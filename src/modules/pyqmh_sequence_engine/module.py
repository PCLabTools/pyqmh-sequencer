"""pyqmh Sequence Engine module for headless sequence execution."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread
from time import sleep
from typing import Any, Optional

from pyqmh import Message, Module, Protocol


class _BreakSequence(Exception):
    """Raised internally when a Break step is encountered."""


class _GotoStep(Exception):
    """Raised internally to jump to a step index in the current sequence."""

    def __init__(self, target_index: int):
        super().__init__(f"Goto index {target_index}")
        self.target_index = target_index


class PyqmhSequenceEngine(Module):
    """Headless sequence engine that executes pyqmh sequence JSON files."""

    _VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")
    _ONLY_VAR_PATTERN = re.compile(r"^\s*\$\{([^}]+)\}\s*$")

    def __init__(self, address: str, protocol: Protocol, debug: Optional[bool] = None):
        super().__init__(address, protocol, debug=debug)
        self._workspace_root = Path(__file__).resolve().parents[3]
        self._sequence_folder_path = self._workspace_root / "doc" / "example sequences"
        self._report_path = self._workspace_root / "doc" / "report.md"
        self._report_enabled = True

        self._loaded_sequence_name: Optional[str] = None
        self._loaded_sequence_path: Optional[Path] = None
        self._loaded_sequence: Optional[dict[str, Any]] = None
        self._loaded_steps: list[dict[str, Any]] = []
        self._step_index_by_id: dict[str, int] = {}
        self._variables: dict[str, Any] = {}

        self._status = "idle"
        self._current_index = 0
        self._current_step_id: Optional[str] = None
        self._last_error: Optional[str] = None

        self._report_entries: list[dict[str, str]] = []
        self._report_tests: list[dict[str, Any]] = []
        self._last_run_started_at: Optional[str] = None
        self._last_run_finished_at: Optional[str] = None

        self._state_lock = Lock()
        self._run_thread: Optional[Thread] = None
        self._pause_requested = False
        self._stop_requested = False
        self._child_threads: list[Thread] = []
        self._prompt_waiting = False
        self._current_prompt: Optional[dict[str, Any]] = None
        self._prompt_response: Optional[dict[str, Any]] = None
        self._prompt_event = Event()

    def handle_message(self, message: Message) -> bool:
        self.logger.debug(f"Handling message: {message}")
        if message.command == "greet":
            return self.greet(message)
        if message.command == "sequence_folder_path":
            return self.sequence_folder_path(message)
        if message.command == "load_sequence":
            return self.load_sequence(message)
        if message.command == "run_sequence":
            return self.run_sequence(message)
        if message.command == "stop_sequence":
            return self.stop_sequence(message)
        if message.command == "pause_sequence":
            return self.pause_sequence(message)
        if message.command == "status":
            return self.status(message)
        if message.command == "get_prompt":
            return self.get_prompt(message)
        if message.command == "confirm_prompt":
            return self.confirm_prompt(message)
        if message.command == "unload_sequence":
            return self.unload_sequence(message)
        if message.command == "report_path":
            return self.report_path(message)
        if message.command == "enable_report":
            return self.enable_report(message)
        if message.command == "get_report":
            return self.get_report(message)
        return super().handle_message(message)

    def background_task(self):
        while self.background_task_running:
            sleep(0.1)

    def _payload_as_dict(self, message: Message) -> dict[str, Any]:
        payload = getattr(message, "payload", None)
        return payload if isinstance(payload, dict) else {}

    def _send_response(self, message: Message, payload: dict[str, Any]):
        """Send response only when the incoming message has a return address."""
        if getattr(message, "source", None) is None:
            return
        self.protocol.send_response(message, payload)

    def _to_display_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self._workspace_root).as_posix()
        except ValueError:
            return str(path.resolve()).replace("\\", "/")

    def _resolve_directory_path(self, raw_path: str) -> Path:
        normalized = str(raw_path or "").strip().replace("\\", "/")
        if not normalized:
            raise ValueError("Path is required")
        path_obj = Path(normalized)
        if path_obj.is_absolute():
            return path_obj.resolve()
        return (self._workspace_root / normalized).resolve()

    def _resolve_sequence_path(self, sequence_name_or_path: str) -> Path:
        normalized = str(sequence_name_or_path or "").strip().replace("\\", "/")
        if not normalized:
            raise ValueError("Sequence name or path is required")
        if not normalized.endswith(".json"):
            normalized = f"{normalized}.json"

        candidate_path = Path(normalized)
        if candidate_path.is_absolute():
            resolved = candidate_path.resolve()
        else:
            resolved = (self._sequence_folder_path / candidate_path).resolve()

        if not resolved.exists() or not resolved.is_file():
            raise ValueError(f"Sequence file not found: {normalized}")
        return resolved

    def _validate_sequence(self, sequence_data: Any):
        if not isinstance(sequence_data, dict):
            raise ValueError("Sequence must be a JSON object")
        if not isinstance(sequence_data.get("metadata"), dict):
            raise ValueError("Sequence metadata must be an object")
        if not isinstance(sequence_data.get("variables"), dict):
            raise ValueError("Sequence variables must be an object")
        if not isinstance(sequence_data.get("sequence"), list):
            raise ValueError("Sequence sequence must be an array")

    def _build_step_index(self, steps: list[dict[str, Any]]) -> dict[str, int]:
        step_index_by_id: dict[str, int] = {}
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValueError(f"Step at index {index} must be an object")
            step_id = str(step.get("ID", "")).strip()
            if not step_id:
                raise ValueError(f"Step at index {index} is missing a valid ID")
            if step_id in step_index_by_id:
                raise ValueError(f"Duplicate step ID: {step_id}")
            step_index_by_id[step_id] = index
        return step_index_by_id

    def _safe_eval(self, expression: str, variables: dict[str, Any]) -> Any:
        safe_globals = {
            "__builtins__": {},
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "float": float,
            "int": int,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "round": round,
            "set": set,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "null": None,
            "true": True,
            "false": False,
        }
        return eval(expression, safe_globals, variables)

    def _replace_expression_vars(self, text: str) -> str:
        return self._VAR_PATTERN.sub(lambda match: match.group(1).strip(), str(text))

    def _resolve_parameter(self, value: Any, variables: dict[str, Any]) -> Any:
        if isinstance(value, str):
            only_var_match = self._ONLY_VAR_PATTERN.match(value)
            if only_var_match is not None:
                expr = self._replace_expression_vars(only_var_match.group(0))
                return self._safe_eval(expr, variables)

            def replace_match(match: re.Match[str]) -> str:
                expr = self._replace_expression_vars(match.group(0))
                resolved = self._safe_eval(expr, variables)
                return "" if resolved is None else str(resolved)

            return self._VAR_PATTERN.sub(replace_match, value)

        if isinstance(value, list):
            return [self._resolve_parameter(item, variables) for item in value]
        if isinstance(value, dict):
            return {key: self._resolve_parameter(item, variables) for key, item in value.items()}
        return value

    def _apply_expression(self, expression: str, variables: dict[str, Any]):
        transformed = self._replace_expression_vars(expression)
        safe_globals = {
            "__builtins__": {},
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "float": float,
            "int": int,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "round": round,
            "set": set,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "null": None,
            "true": True,
            "false": False,
        }
        exec(transformed, safe_globals, variables)

    def _report_append(self, entry: str):
        timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with self._state_lock:
            self._report_entries.append({"timestamp": timestamp, "entry": str(entry)})

    def _report_result_append(self, test_name: str, result: Any):
        with self._state_lock:
            self._report_tests.append({"test": str(test_name), "result": result})

    def _build_report_markdown(self) -> str:
        with self._state_lock:
            sequence_id = None
            if isinstance(self._loaded_sequence, dict):
                metadata = self._loaded_sequence.get("metadata")
                if isinstance(metadata, dict):
                    sequence_id = metadata.get("sequence id")
            if not sequence_id:
                sequence_id = self._loaded_sequence_name or "sequence"

            lines = [f"# {sequence_id} Report", "", "## Information", ""]
            lines.append(f"Sequence: {self._loaded_sequence_name or 'unloaded'}")
            lines.append(f"Status: {self._status}")
            lines.append(f"Started: {self._last_run_started_at or ''}")
            lines.append(f"Finished: {self._last_run_finished_at or ''}")
            lines.append("")
            lines.append("## Tests")
            lines.append("")
            lines.append("| Test | Result |")
            lines.append("| ---- | ------ |")
            for row in self._report_tests:
                lines.append(f"| {row['test']} | {row['result']} |")
            lines.append("")
            lines.append("## Results")
            lines.append("")
            for row in self._report_entries:
                lines.append(f"{row['timestamp']}: {row['entry']}")
            lines.append("")
            return "\n".join(lines)

    def _write_report_file(self):
        if not self._report_enabled:
            return
        report_text = self._build_report_markdown()
        self._report_path.parent.mkdir(parents=True, exist_ok=True)
        with self._report_path.open("w", encoding="utf-8") as handle:
            handle.write(report_text)

    def _as_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _step_type(self, step: dict[str, Any]) -> str:
        return str(step.get("Type", "")).strip().lower()

    def _wait_if_paused_or_stopped(self):
        while True:
            with self._state_lock:
                if self._stop_requested:
                    raise InterruptedError("Sequence stop requested")
                paused = self._pause_requested
            if not paused:
                return
            sleep(0.05)

    def _resolve_goto_index(self, value: Any, step_index_by_id: dict[str, int], step_count: int) -> int:
        if isinstance(value, str):
            step_id = value.strip()
            if not step_id:
                raise ValueError("Goto Step is empty")
            if step_id not in step_index_by_id:
                raise ValueError(f"Goto target step ID not found: {step_id}")
            return step_index_by_id[step_id]

        if isinstance(value, (int, float)):
            index = int(value)
            if 0 <= index < step_count:
                return index
            if 1 <= index <= step_count:
                return index - 1
            raise ValueError(f"Goto index out of range: {index}")

        raise ValueError("Goto Step must be a step ID string or numeric index")

    def _execute_steps(
        self,
        steps: list[dict[str, Any]],
        variables: dict[str, Any],
        step_index_by_id: Optional[dict[str, int]] = None,
        goto_index_by_id: Optional[dict[str, int]] = None,
        goto_step_count: Optional[int] = None,
        track_main_position: bool = False,
        base_path: Optional[Path] = None,
        start_index: int = 0,
    ):
        if step_index_by_id is None:
            step_index_by_id = self._build_step_index(steps)
        if goto_index_by_id is None:
            goto_index_by_id = step_index_by_id
        if goto_step_count is None:
            goto_step_count = len(steps)

        index = max(0, start_index)
        while index < len(steps):
            self._wait_if_paused_or_stopped()

            step = steps[index]
            step_type = self._step_type(step)
            step_id = str(step.get("ID", "")).strip() or f"index_{index}"

            if track_main_position:
                with self._state_lock:
                    self._current_index = index
                    self._current_step_id = step_id

            if step_type == "label":
                index += 1
                continue

            if step_type == "set":
                variable_name = str(step.get("Variable", "")).strip()
                if not variable_name:
                    raise ValueError(f"Step {step_id}: Set requires Variable")
                variables[variable_name] = self._resolve_parameter(step.get("Value"), variables)
                index += 1
                continue

            if step_type == "expression":
                expression = str(step.get("Expression", "")).strip()
                if not expression:
                    raise ValueError(f"Step {step_id}: Expression requires Expression text")
                self._apply_expression(expression, variables)
                index += 1
                continue

            if step_type == "goto":
                target = self._resolve_parameter(step.get("Step"), variables)
                raise _GotoStep(self._resolve_goto_index(target, goto_index_by_id, goto_step_count))

            if step_type == "action":
                module_id = str(self._resolve_parameter(step.get("Module ID"), variables) or "").strip()
                action = str(self._resolve_parameter(step.get("Action"), variables) or "").strip()
                arguments = step.get("Arguments", {})
                payload = self._resolve_parameter(arguments if isinstance(arguments, dict) else {}, variables)
                if not module_id or not action:
                    raise ValueError(f"Step {step_id}: Action requires Module ID and Action")
                self.protocol.send_action(module_id, action, payload=payload)
                index += 1
                continue

            if step_type == "request":
                module_id = str(self._resolve_parameter(step.get("Module ID"), variables) or "").strip()
                action = str(self._resolve_parameter(step.get("Action"), variables) or "").strip()
                arguments = step.get("Arguments", {})
                payload = self._resolve_parameter(arguments if isinstance(arguments, dict) else {}, variables)
                timeout_ms = self._resolve_parameter(step.get("Timeout"), variables) if "Timeout" in step else None
                timeout_seconds = None
                if timeout_ms is not None:
                    timeout_seconds = max(0.0, float(timeout_ms) / 1000.0)

                if not module_id or not action:
                    raise ValueError(f"Step {step_id}: Request requires Module ID and Action")

                response: dict[str, Any] = {}
                try:
                    if timeout_seconds is None:
                        response = self.protocol.send_request(module_id, action, payload=payload)
                    else:
                        response = self.protocol.send_request(module_id, action, payload=payload, timeout=timeout_seconds)
                except TimeoutError:
                    on_timeout = step.get("OnTimeout", [])
                    if isinstance(on_timeout, list) and on_timeout:
                        self._execute_steps(
                            on_timeout,
                            variables,
                            goto_index_by_id=goto_index_by_id,
                            goto_step_count=goto_step_count,
                            base_path=base_path,
                        )
                    index += 1
                    continue

                return_map = step.get("Return", {})
                if isinstance(return_map, dict) and isinstance(response, dict):
                    for response_key, variable_name in return_map.items():
                        variable_id = str(variable_name).strip()
                        if variable_id:
                            variables[variable_id] = response.get(response_key)
                index += 1
                continue

            if step_type == "for":
                iterations = int(self._resolve_parameter(step.get("Iterations", 0), variables))
                sub_sequence = step.get("SubSequence", [])
                loop_index_var = str(step.get("Index", "")).strip()
                if not isinstance(sub_sequence, list):
                    raise ValueError(f"Step {step_id}: For SubSequence must be an array")
                for loop_index in range(max(0, iterations)):
                    self._wait_if_paused_or_stopped()
                    if loop_index_var:
                        variables[loop_index_var] = loop_index
                    try:
                        self._execute_steps(
                            sub_sequence,
                            variables,
                            goto_index_by_id=goto_index_by_id,
                            goto_step_count=goto_step_count,
                            base_path=base_path,
                        )
                    except _BreakSequence:
                        break
                index += 1
                continue

            if step_type == "for each":
                raw_array = self._resolve_parameter(step.get("Array", []), variables)
                if not isinstance(raw_array, list):
                    raise ValueError(f"Step {step_id}: For Each Array must evaluate to an array")
                element_var = str(step.get("Element", "")).strip()
                index_var = str(step.get("Index", "")).strip()
                sub_sequence = step.get("SubSequence", [])
                if not element_var:
                    raise ValueError(f"Step {step_id}: For Each requires Element")
                if not isinstance(sub_sequence, list):
                    raise ValueError(f"Step {step_id}: For Each SubSequence must be an array")
                for loop_index, element in enumerate(raw_array):
                    self._wait_if_paused_or_stopped()
                    variables[element_var] = element
                    if index_var:
                        variables[index_var] = loop_index
                    try:
                        self._execute_steps(
                            sub_sequence,
                            variables,
                            goto_index_by_id=goto_index_by_id,
                            goto_step_count=goto_step_count,
                            base_path=base_path,
                        )
                    except _BreakSequence:
                        break
                index += 1
                continue

            if step_type == "while":
                condition_expr = self._replace_expression_vars(str(step.get("Condition", "False")))
                sub_sequence = step.get("SubSequence", [])
                index_var = str(step.get("Index", "")).strip()
                if not isinstance(sub_sequence, list):
                    raise ValueError(f"Step {step_id}: While SubSequence must be an array")
                loop_index = 0
                while True:
                    self._wait_if_paused_or_stopped()
                    should_break = bool(self._safe_eval(condition_expr, variables))
                    if should_break:
                        break
                    if index_var:
                        variables[index_var] = loop_index
                    loop_index += 1
                    try:
                        self._execute_steps(
                            sub_sequence,
                            variables,
                            goto_index_by_id=goto_index_by_id,
                            goto_step_count=goto_step_count,
                            base_path=base_path,
                        )
                    except _BreakSequence:
                        break
                index += 1
                continue

            if step_type == "do while":
                condition_expr = self._replace_expression_vars(str(step.get("Condition", "False")))
                sub_sequence = step.get("SubSequence", [])
                index_var = str(step.get("Index", "")).strip()
                if not isinstance(sub_sequence, list):
                    raise ValueError(f"Step {step_id}: Do While SubSequence must be an array")
                loop_index = 0
                while True:
                    self._wait_if_paused_or_stopped()
                    if index_var:
                        variables[index_var] = loop_index
                    loop_index += 1
                    try:
                        self._execute_steps(
                            sub_sequence,
                            variables,
                            goto_index_by_id=goto_index_by_id,
                            goto_step_count=goto_step_count,
                            base_path=base_path,
                        )
                    except _BreakSequence:
                        break
                    should_break = bool(self._safe_eval(condition_expr, variables))
                    if should_break:
                        break
                index += 1
                continue

            if step_type == "break":
                raise _BreakSequence()

            if step_type == "if":
                condition_expr = self._replace_expression_vars(str(step.get("Condition", "False")))
                branch_true = step.get("OnTrue", [])
                branch_false = step.get("OnFalse", [])
                if not isinstance(branch_true, list) or not isinstance(branch_false, list):
                    raise ValueError(f"Step {step_id}: If branches must be arrays")
                branch = branch_true if bool(self._safe_eval(condition_expr, variables)) else branch_false
                self._execute_steps(
                    branch,
                    variables,
                    goto_index_by_id=goto_index_by_id,
                    goto_step_count=goto_step_count,
                    base_path=base_path,
                )
                index += 1
                continue

            if step_type == "call":
                call_target = self._resolve_parameter(step.get("Sequence"), variables)
                threaded = self._as_bool(self._resolve_parameter(step.get("Threaded", False), variables))
                arguments = step.get("Arguments", {})

                if not isinstance(call_target, str) or not call_target.strip():
                    raise ValueError(f"Step {step_id}: Call requires Sequence path")

                call_path_raw = call_target.strip().replace("\\", "/")
                if not call_path_raw.endswith(".json"):
                    call_path_raw = f"{call_path_raw}.json"

                path_obj = Path(call_path_raw)
                if path_obj.is_absolute():
                    call_path = path_obj.resolve()
                else:
                    root = base_path if base_path is not None else self._sequence_folder_path
                    call_path = (root / path_obj).resolve()

                if not call_path.exists() or not call_path.is_file():
                    raise ValueError(f"Step {step_id}: Called sequence not found: {call_path_raw}")

                with call_path.open("r", encoding="utf-8") as handle:
                    called_sequence = json.load(handle)
                self._validate_sequence(called_sequence)

                child_vars = dict(called_sequence.get("variables", {}))
                parent_bindings: dict[str, str] = {}

                if isinstance(arguments, dict):
                    for child_var, arg_value in arguments.items():
                        if isinstance(arg_value, str):
                            match = self._ONLY_VAR_PATTERN.match(arg_value)
                            if match is not None:
                                parent_name = match.group(1).strip()
                                if parent_name in variables:
                                    parent_bindings[str(child_var)] = parent_name
                                    child_vars[str(child_var)] = variables[parent_name]
                                    continue
                        child_vars[str(child_var)] = self._resolve_parameter(arg_value, variables)

                child_steps = called_sequence.get("sequence", [])
                if not isinstance(child_steps, list):
                    raise ValueError(f"Step {step_id}: Called sequence steps must be an array")

                def run_child_sequence():
                    child_step_index = self._build_step_index(child_steps)
                    child_start_index = 0
                    while child_start_index < len(child_steps):
                        try:
                            self._execute_steps(
                                child_steps,
                                child_vars,
                                step_index_by_id=child_step_index,
                                goto_index_by_id=child_step_index,
                                goto_step_count=len(child_steps),
                                base_path=call_path.parent,
                                start_index=child_start_index,
                            )
                            break
                        except _GotoStep as goto_target:
                            # Keep Goto scoped to the called child sequence.
                            child_start_index = goto_target.target_index
                            continue
                    for child_var, parent_var in parent_bindings.items():
                        variables[parent_var] = child_vars.get(child_var)

                if threaded:
                    child_thread = Thread(target=run_child_sequence, daemon=True)
                    child_thread.start()
                    self._child_threads.append(child_thread)
                else:
                    run_child_sequence()

                index += 1
                continue

            if step_type == "report":
                entry = self._resolve_parameter(step.get("Entry", ""), variables)
                self._report_append(str(entry))
                index += 1
                continue

            if step_type == "report result":
                test_name = self._resolve_parameter(step.get("Test", ""), variables)
                result = self._resolve_parameter(step.get("Result", ""), variables)
                self._report_result_append(str(test_name), result)
                index += 1
                continue

            if step_type == "wait":
                wait_seconds = float(self._resolve_parameter(step.get("Time", 0), variables))
                slept = 0.0
                # Keep waits interruptible so pause/stop commands remain responsive.
                while slept < max(0.0, wait_seconds):
                    self._wait_if_paused_or_stopped()
                    increment = min(0.05, max(0.0, wait_seconds) - slept)
                    sleep(increment)
                    slept += increment
                index += 1
                continue

            if step_type == "prompt":
                return_var = str(step.get("Return", "")).strip()
                prompt_type = str(step.get("PromptType", "CONFIRM")).strip().upper()
                if not return_var:
                    raise ValueError(f"Step {step_id}: Prompt requires Return variable")

                title = self._resolve_parameter(step.get("Title", ""), variables)
                prompt_message = self._resolve_parameter(step.get("Message", ""), variables)
                prompt_payload = {
                    "step_id": step_id,
                    "title": "" if title is None else str(title),
                    "message": "" if prompt_message is None else str(prompt_message),
                    "prompt_type": prompt_type,
                    "return": return_var,
                }

                with self._state_lock:
                    self._prompt_waiting = True
                    self._current_prompt = prompt_payload
                    self._prompt_response = None
                    self._prompt_event.clear()

                while True:
                    with self._state_lock:
                        if self._stop_requested:
                            raise InterruptedError("Sequence stop requested")
                    if self._prompt_event.wait(0.05):
                        break

                with self._state_lock:
                    prompt_response = dict(self._prompt_response or {})
                    self._prompt_waiting = False
                    self._current_prompt = None
                    self._prompt_response = None
                    self._prompt_event.clear()

                response_value = prompt_response.get("value", prompt_response.get("response", prompt_response.get("input")))
                if response_value is None:
                    if "confirmed" in prompt_response:
                        response_value = prompt_response.get("confirmed")
                    elif "ok" in prompt_response:
                        response_value = prompt_response.get("ok")
                    elif "cancelled" in prompt_response:
                        response_value = not bool(prompt_response.get("cancelled"))

                if prompt_type == "CONFIRM":
                    result = True if response_value is None else bool(response_value)
                elif prompt_type == "OK/CANCEL":
                    result = bool(response_value)
                elif prompt_type == "STRING":
                    result = "" if response_value is None else str(response_value)
                elif prompt_type == "NUMBER":
                    if response_value is None or response_value == "":
                        result = 0
                    else:
                        try:
                            numeric = float(response_value)
                        except (TypeError, ValueError):
                            raise ValueError(f"Step {step_id}: Prompt NUMBER received non-numeric response")
                        result = int(numeric) if numeric.is_integer() else numeric
                else:
                    result = response_value

                variables[return_var] = result
                self._report_append(f"Prompt {prompt_type} completed")
                index += 1
                continue

            if step_type == "cli":
                command = str(self._resolve_parameter(step.get("Command", ""), variables) or "").strip()
                return_var = str(step.get("Return", "")).strip()
                if not command:
                    raise ValueError(f"Step {step_id}: CLI requires Command")
                completed = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                output_text = (completed.stdout or "") + (completed.stderr or "")
                if return_var:
                    variables[return_var] = output_text.strip()
                index += 1
                continue

            raise ValueError(f"Step {step_id}: Unsupported step type '{step.get('Type')}'")

    def _run_loaded_sequence(self):
        try:
            with self._state_lock:
                self._status = "running"
                self._last_error = None
                self._last_run_started_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
                self._last_run_finished_at = None
                steps = list(self._loaded_steps)
                variables = self._variables
                step_index_by_id = dict(self._step_index_by_id)
                sequence_base_path = self._loaded_sequence_path.parent if self._loaded_sequence_path else self._sequence_folder_path

            while True:
                with self._state_lock:
                    start_index = self._current_index
                if start_index >= len(steps):
                    break

                try:
                    # Execute from current index so pause/resume can continue from where it stopped.
                    self._execute_steps(
                        steps,
                        variables,
                        step_index_by_id=step_index_by_id,
                        goto_index_by_id=step_index_by_id,
                        goto_step_count=len(steps),
                        track_main_position=True,
                        base_path=sequence_base_path,
                        start_index=start_index,
                    )
                    break
                except _GotoStep as goto_target:
                    with self._state_lock:
                        self._current_index = goto_target.target_index
                    continue

            with self._state_lock:
                if self._stop_requested:
                    self._status = "stopped"
                elif self._pause_requested:
                    self._status = "paused"
                else:
                    self._status = "completed"
                    self._current_index = len(self._loaded_steps)
                self._last_run_finished_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        except InterruptedError:
            with self._state_lock:
                self._status = "stopped" if self._stop_requested else "paused"
                self._last_run_finished_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        except Exception as exc:
            self.logger.exception("Sequence execution failed")
            self._report_append(f"ERROR: {exc}")
            with self._state_lock:
                self._status = "error"
                self._last_error = str(exc)
                self._last_run_finished_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        finally:
            with self._state_lock:
                self._prompt_waiting = False
                self._current_prompt = None
                self._prompt_response = None
                self._prompt_event.set()
            self._write_report_file()
            with self._state_lock:
                self._run_thread = None
                self._stop_requested = False

    def sequence_folder_path(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        raw_path = payload.get("path", payload.get("sequence_folder_path", payload.get("folder")))
        try:
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError("path is required")
            resolved = self._resolve_directory_path(raw_path)
            if not resolved.exists() or not resolved.is_dir():
                raise ValueError("Directory does not exist")
            with self._state_lock:
                self._sequence_folder_path = resolved
        except ValueError as exc:
            self._send_response(message, {"ok": False, "error": str(exc)})
            return False

        self._send_response(
            message,
            {
                "ok": True,
                "sequence_folder_path": self._to_display_path(self._sequence_folder_path),
            },
        )
        return False

    def load_sequence(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        sequence_ref = payload.get("name", payload.get("sequence", payload.get("path")))
        try:
            if not isinstance(sequence_ref, str) or not sequence_ref.strip():
                raise ValueError("name/sequence/path is required")

            sequence_path = self._resolve_sequence_path(sequence_ref)
            with sequence_path.open("r", encoding="utf-8") as handle:
                sequence_data = json.load(handle)

            self._validate_sequence(sequence_data)
            steps = sequence_data.get("sequence", [])
            step_index_by_id = self._build_step_index(steps)
            sequence_name = sequence_data.get("metadata", {}).get("sequence id") or sequence_path.stem

            with self._state_lock:
                self._loaded_sequence_name = str(sequence_name)
                self._loaded_sequence_path = sequence_path
                self._loaded_sequence = sequence_data
                self._loaded_steps = steps
                self._step_index_by_id = step_index_by_id
                self._variables = dict(sequence_data.get("variables", {}))
                self._current_index = 0
                self._current_step_id = None
                self._status = "loaded"
                self._last_error = None
                self._pause_requested = False
                self._stop_requested = False
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            self._send_response(message, {"ok": False, "error": str(exc)})
            return False

        self._send_response(
            message,
            {
                "ok": True,
                "loaded_sequence": self._loaded_sequence_name,
                "path": self._to_display_path(self._loaded_sequence_path),
                "steps": len(self._loaded_steps),
            },
        )
        return False

    def run_sequence(self, message: Message) -> bool:
        with self._state_lock:
            if self._loaded_sequence is None:
                self._send_response(message, {"ok": False, "error": "No sequence loaded"})
                return False

            if self._run_thread is not None and self._run_thread.is_alive() and self._status == "running":
                self._send_response(message, {"ok": True, "status": "already running"})
                return False

            if self._status == "paused":
                self._pause_requested = False
                self._status = "running"
                self._send_response(
                    message,
                    {
                        "ok": True,
                        "status": "running",
                        "resumed": True,
                        "sequence": self._loaded_sequence_name,
                    },
                )
                return False

            if self._status in {"completed", "stopped", "error"} and self._current_index >= len(self._loaded_steps):
                self._current_index = 0
                self._variables = dict(self._loaded_sequence.get("variables", {})) if self._loaded_sequence else {}

            self._pause_requested = False
            self._stop_requested = False

            if self._run_thread is None or not self._run_thread.is_alive():
                self._run_thread = Thread(target=self._run_loaded_sequence, daemon=True)
                self._run_thread.start()

        self._send_response(
            message,
            {
                "ok": True,
                "status": "running",
                "resumed": False,
                "sequence": self._loaded_sequence_name,
            },
        )
        return False

    def stop_sequence(self, message: Message) -> bool:
        with self._state_lock:
            self._stop_requested = True
            self._pause_requested = False
            self._prompt_event.set()
            if self._status in {"running", "paused"}:
                self._status = "stopping"

        self._send_response(
            message,
            {
                "ok": True,
                "status": "stopping",
            },
        )
        return False

    def pause_sequence(self, message: Message) -> bool:
        with self._state_lock:
            if self._status != "running":
                self._send_response(
                    message,
                    {
                        "ok": False,
                        "error": "Sequence is not running",
                    },
                )
                return False
            self._pause_requested = True
            self._status = "paused"

        self._send_response(
            message,
            {
                "ok": True,
                "status": "paused",
            },
        )
        return False

    def status(self, message: Message) -> bool:
        with self._state_lock:
            response = {
                "ok": True,
                "status": self._status,
                "sequence_folder_path": self._to_display_path(self._sequence_folder_path),
                "loaded_sequence": self._loaded_sequence_name,
                "loaded_sequence_path": self._to_display_path(self._loaded_sequence_path) if self._loaded_sequence_path else None,
                "report_enabled": self._report_enabled,
                "report_path": self._to_display_path(self._report_path),
                "current_index": self._current_index,
                "current_step_id": self._current_step_id,
                "total_steps": len(self._loaded_steps),
                "variables": dict(self._variables),
                "prompt_waiting": self._prompt_waiting,
                "prompt": dict(self._current_prompt) if isinstance(self._current_prompt, dict) else None,
                "last_error": self._last_error,
                "last_run_started_at": self._last_run_started_at,
                "last_run_finished_at": self._last_run_finished_at,
            }

        self._send_response(message, response)
        return False

    def unload_sequence(self, message: Message) -> bool:
        with self._state_lock:
            self._stop_requested = True
            self._pause_requested = False
            self._prompt_waiting = False
            self._current_prompt = None
            self._prompt_response = None
            self._prompt_event.set()
            self._loaded_sequence_name = None
            self._loaded_sequence_path = None
            self._loaded_sequence = None
            self._loaded_steps = []
            self._step_index_by_id = {}
            self._variables = {}
            self._current_index = 0
            self._current_step_id = None
            self._status = "idle"
            self._last_error = None
            self._last_run_started_at = None
            self._last_run_finished_at = None
            self._report_entries = []
            self._report_tests = []

        self._send_response(
            message,
            {
                "ok": True,
                "status": "idle",
                "loaded_sequence": None,
            },
        )
        return False

    def report_path(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        raw_path = payload.get("path", payload.get("report_path"))
        try:
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError("path is required")
            resolved = self._resolve_directory_path(raw_path)
            if resolved.suffix.lower() != ".md":
                resolved = resolved / "report.md" if resolved.is_dir() or not resolved.suffix else resolved
            with self._state_lock:
                self._report_path = resolved
        except ValueError as exc:
            self._send_response(message, {"ok": False, "error": str(exc)})
            return False

        self._send_response(
            message,
            {
                "ok": True,
                "report_path": self._to_display_path(self._report_path),
            },
        )
        return False

    def enable_report(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        enabled = payload.get("enabled", payload.get("enable", payload.get("value", True)))
        with self._state_lock:
            self._report_enabled = self._as_bool(enabled)

        self._send_response(
            message,
            {
                "ok": True,
                "report_enabled": self._report_enabled,
            },
        )
        return False

    def get_report(self, message: Message) -> bool:
        report_text = self._build_report_markdown()
        with self._state_lock:
            response = {
                "ok": True,
                "report": report_text,
                "entries": list(self._report_entries),
                "tests": list(self._report_tests),
                "report_path": self._to_display_path(self._report_path),
                "report_enabled": self._report_enabled,
            }
        self._send_response(message, response)
        return False

    def get_prompt(self, message: Message) -> bool:
        with self._state_lock:
            response = {
                "ok": True,
                "prompt_waiting": self._prompt_waiting,
                "prompt": dict(self._current_prompt) if isinstance(self._current_prompt, dict) else None,
            }
        self._send_response(message, response)
        return False

    def confirm_prompt(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        with self._state_lock:
            if not self._prompt_waiting or self._current_prompt is None:
                self._send_response(
                    message,
                    {
                        "ok": False,
                        "error": "No prompt is currently waiting",
                    },
                )
                return False

            self._prompt_response = dict(payload)
            self._prompt_event.set()
            prompt_snapshot = dict(self._current_prompt)

        self._send_response(
            message,
            {
                "ok": True,
                "prompt_waiting": True,
                "prompt": prompt_snapshot,
            },
        )
        return False

    def greet(self, message: Message) -> bool:
        self._send_response(
            message,
            {
                "module": self.address,
                "commands": [
                    "sequence_folder_path",
                    "load_sequence",
                    "run_sequence",
                    "stop_sequence",
                    "pause_sequence",
                    "status",
                    "get_prompt",
                    "confirm_prompt",
                    "unload_sequence",
                    "report_path",
                    "enable_report",
                    "get_report",
                ],
            },
        )
        return False

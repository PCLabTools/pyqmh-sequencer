"""pyqmh Sequence Editor module for sequence file management requests."""

import json
from pathlib import Path
from time import sleep
from typing import Any, Optional

from pyqmh import Message, Module, Protocol


class PyqmhSequenceEditor(Module):
    """
    PyqmhSequenceEditor is a module that extends the base Module class from the Queued Message Handling (QMH) Framework. It provides custom message handling and background task functionality.
    """

    def __init__(
        self,
        address: str,
        protocol: Protocol,
        debug: Optional[bool] = None,
        default_sequence_dir: Optional[str] = None,
    ):
        """Initialises the module and sets up the protocol.

        Args:
            address (str): The address of the module.
            protocol (Protocol): The protocol instance.
            debug (Optional[bool]): If provided, overrides logger level for this module.
            default_sequence_dir (Optional[str]): Workspace-relative directory used for sequence listing.
        """
        super().__init__(address, protocol, debug=debug)
        self._workspace_root = Path(__file__).resolve().parents[3]
        self._default_sequence_dirs = [
            self._workspace_root / "doc" / "example sequences",
            self._workspace_root / "sequences",
        ]
        self._sequence_directory = self._resolve_initial_sequence_directory(default_sequence_dir)
        self._module_commands: dict[str, dict[str, list[dict[str, list[str]]]]] = {}

    def handle_message(self, message: Message) -> bool:
        """Handle incoming messages.

        Args:
            message (Message): The message to handle.

        Returns:
            bool: True if the module should shutdown, False otherwise.
        """
        self.logger.debug(f"Handling message: {message}")
        if message.command == "greet":
            return self.greet(message)
        if message.command == "list_sequences":
            return self.list_sequences(message)
        if message.command == "load_sequence":
            return self.load_sequence(message)
        if message.command == "save_sequence":
            return self.save_sequence(message)
        if message.command == "get_sequence_directory":
            return self.get_sequence_directory(message)
        if message.command == "set_sequence_directory":
            return self.set_sequence_directory(message)
        if message.command == "browse_sequence_directory":
            return self.browse_sequence_directory(message)
        if message.command == "set_module_commands":
            return self.set_module_commands(message)
        return super().handle_message(message)

    def _normalize_command_entries(self, entries: Any, entry_kind: str) -> list[dict[str, list[str]]]:
        if not isinstance(entries, list):
            raise ValueError(f"{entry_kind} must be an array")

        normalized_entries: list[dict[str, list[str]]] = []
        for entry in entries:
            if not isinstance(entry, dict) or len(entry) != 1:
                raise ValueError(f"Each {entry_kind} entry must be an object with exactly one command")

            command_name, argument_names = next(iter(entry.items()))
            if not isinstance(command_name, str) or not command_name.strip():
                raise ValueError(f"Each {entry_kind} command name must be a non-empty string")
            if not isinstance(argument_names, list) or not all(
                isinstance(argument_name, str) and argument_name.strip() for argument_name in argument_names
            ):
                raise ValueError(f"Each {entry_kind} command field list must contain non-empty strings")

            normalized_entries.append(
                {
                    command_name.strip(): [argument_name.strip() for argument_name in argument_names],
                }
            )

        return normalized_entries

    def _normalize_module_commands(self, raw_commands: Any) -> dict[str, dict[str, list[dict[str, list[str]]]]]:
        if not isinstance(raw_commands, dict):
            raise ValueError("module_commands must be an object")

        normalized_commands: dict[str, dict[str, list[dict[str, list[str]]]]] = {}
        for module_name, module_commands in raw_commands.items():
            if not isinstance(module_name, str) or not module_name.strip():
                raise ValueError("Each module name must be a non-empty string")
            if not isinstance(module_commands, dict):
                raise ValueError(f"Commands for module '{module_name}' must be an object")

            normalized_commands[module_name.strip()] = {
                "actions": self._normalize_command_entries(module_commands.get("actions", []), "actions"),
                "requests": self._normalize_command_entries(module_commands.get("requests", []), "requests"),
                "responses": self._normalize_command_entries(module_commands.get("responses", []), "responses"),
            }

        return normalized_commands

    def _resolve_initial_sequence_directory(self, default_sequence_dir: Optional[str]) -> Path:
        if isinstance(default_sequence_dir, str) and default_sequence_dir.strip():
            return self._resolve_safe_directory(default_sequence_dir.strip())

        for candidate in self._default_sequence_dirs:
            if candidate.exists() and candidate.is_dir():
                return candidate
        return self._default_sequence_dirs[0]

    def _payload_as_dict(self, message: Message) -> dict[str, Any]:
        payload = getattr(message, "payload", None)
        return payload if isinstance(payload, dict) else {}

    def _to_display_path(self, path: Path) -> str:
        try:
            return path.relative_to(self._workspace_root).as_posix()
        except ValueError:
            return str(path).replace("\\", "/")

    def _resolve_safe_path(self, raw_path: str) -> Path:
        normalized = str(raw_path or "").strip().replace("\\", "/")
        if not normalized:
            raise ValueError("Path is required")
        if not normalized.endswith(".json"):
            normalized = f"{normalized}.json"

        path_obj = Path(normalized)
        if path_obj.is_absolute():
            candidate = path_obj.resolve()
        else:
            candidate = (self._workspace_root / normalized).resolve()
        return candidate

    def _resolve_safe_directory(self, raw_path: str) -> Path:
        normalized = str(raw_path or "").strip().replace("\\", "/")
        if not normalized:
            raise ValueError("Directory is required")

        path_obj = Path(normalized)
        if path_obj.is_absolute():
            candidate = path_obj.resolve()
        else:
            candidate = (self._workspace_root / normalized).resolve()
        return candidate

    def _validate_sequence_payload(self, sequence_data: Any):
        if not isinstance(sequence_data, dict):
            raise ValueError("Sequence must be a JSON object")
        if not isinstance(sequence_data.get("metadata"), dict):
            raise ValueError("Sequence metadata must be an object")
        if not isinstance(sequence_data.get("variables"), dict):
            raise ValueError("Sequence variables must be an object")
        if not isinstance(sequence_data.get("sequence"), list):
            raise ValueError("Sequence sequence must be an array")

    def list_sequences(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        requested_dir = payload.get("directory")

        directories: list[Path] = []
        if isinstance(requested_dir, str) and requested_dir.strip():
            try:
                directories.append(self._resolve_safe_directory(requested_dir.strip()))
            except ValueError as exc:
                self.protocol.send_response(message, {"ok": False, "error": str(exc)})
                return False
        else:
            directories.append(self._sequence_directory)

        files: list[str] = []
        for directory in directories:
            if not directory.exists() or not directory.is_dir():
                continue
            for path in sorted(directory.rglob("*.json")):
                if path.is_file():
                    files.append(self._to_display_path(path))

        self.protocol.send_response(
            message,
            {
                "ok": True,
                "files": sorted(set(files)),
                "workspace_root": str(self._workspace_root),
                "current_directory": self._to_display_path(self._sequence_directory),
            },
        )
        return False

    def get_sequence_directory(self, message: Message) -> bool:
        self.protocol.send_response(
            message,
            {
                "ok": True,
                "directory": self._to_display_path(self._sequence_directory),
            },
        )
        return False

    def set_sequence_directory(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        raw_directory = payload.get("directory")

        try:
            if not isinstance(raw_directory, str) or not raw_directory.strip():
                raise ValueError("Directory is required")
            resolved = self._resolve_safe_directory(raw_directory.strip())
            if not resolved.exists() or not resolved.is_dir():
                raise ValueError("Directory does not exist")
            self._sequence_directory = resolved
        except ValueError as exc:
            self.protocol.send_response(message, {"ok": False, "error": str(exc)})
            return False

        self.protocol.send_response(
            message,
            {
                "ok": True,
                "directory": self._to_display_path(self._sequence_directory),
            },
        )
        return False

    def browse_sequence_directory(self, message: Message) -> bool:
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected_dir = filedialog.askdirectory(
                title="Select sequence directory",
                initialdir=str(self._sequence_directory),
            )
            root.destroy()
        except Exception as exc:
            self.protocol.send_response(message, {"ok": False, "error": f"Folder prompt failed: {exc}"})
            return False

        if not selected_dir:
            self.protocol.send_response(
                message,
                {
                    "ok": True,
                    "cancelled": True,
                    "directory": self._to_display_path(self._sequence_directory),
                },
            )
            return False

        try:
            resolved = self._resolve_safe_directory(selected_dir)
            if not resolved.exists() or not resolved.is_dir():
                raise ValueError("Selected folder does not exist")
            self._sequence_directory = resolved
        except ValueError as exc:
            self.protocol.send_response(message, {"ok": False, "error": str(exc)})
            return False

        self.protocol.send_response(
            message,
            {
                "ok": True,
                "directory": self._to_display_path(self._sequence_directory),
            },
        )
        return False

    def set_module_commands(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)

        try:
            raw_commands = payload.get("module_commands") if "module_commands" in payload else payload
            self._module_commands = self._normalize_module_commands(raw_commands)
        except ValueError as exc:
            if message.source is not None:
                self.protocol.send_response(message, {"ok": False, "error": str(exc)})
            return False

        if message.source is not None:
            self.protocol.send_response(
                message,
                {
                    "ok": True,
                    "module_commands": self._module_commands,
                },
            )
        return False

    def load_sequence(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        raw_path = payload.get("path")

        try:
            file_path = self._resolve_safe_path(str(raw_path or ""))
            with file_path.open("r", encoding="utf-8") as handle:
                sequence_data = json.load(handle)
            self._validate_sequence_payload(sequence_data)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            self.protocol.send_response(message, {"ok": False, "error": str(exc)})
            return False

        self.protocol.send_response(
            message,
            {
                "ok": True,
                "path": self._to_display_path(file_path),
                "sequence": sequence_data,
            },
        )
        return False

    def save_sequence(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        raw_path = payload.get("path")
        overwrite = bool(payload.get("overwrite", False))
        sequence_data = payload.get("sequence")

        try:
            self._validate_sequence_payload(sequence_data)
            file_path = self._resolve_safe_path(str(raw_path or ""))
            if file_path.exists() and not overwrite:
                raise ValueError("File already exists. Set overwrite=true to replace it.")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with file_path.open("w", encoding="utf-8") as handle:
                json.dump(sequence_data, handle, indent=2)
        except (OSError, ValueError, TypeError) as exc:
            self.protocol.send_response(message, {"ok": False, "error": str(exc)})
            return False

        self.protocol.send_response(
            message,
            {
                "ok": True,
                "path": self._to_display_path(file_path),
            },
        )
        return False

    def background_task(self):
        """Background task that runs while the module is active."""
        while self.background_task_running:
            self.logger.debug("Running background task.")
            # TODO: implement background task logic
            sleep(1)

    def greet(self, message: Message) -> bool:
        """Handles the "greet" message.

        Args:
            message (Message): Incoming message to handle.

        Returns:
            bool: False to indicate that the module should continue running.
        """
        self.logger.debug(f"Handling greet message: {message}")
        self.protocol.send_response(
            message,
            {
                "module": self.address,
                "commands": [
                    "list_sequences",
                    "load_sequence",
                    "save_sequence",
                    "get_sequence_directory",
                    "set_sequence_directory",
                    "browse_sequence_directory",
                    "set_module_commands",
                ],
                "module_commands": self._module_commands,
            },
        )
        return False
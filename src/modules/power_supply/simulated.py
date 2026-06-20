"""Simulated implementation of PowerSupply for development and testing."""

from threading import Lock
from time import sleep
from typing import Any

from pyqmh import Message

from .base import BasePowerSupply
from .factory import PowerSupply


class SimulatedPowerSupply(BasePowerSupply):
    """Simple simulated single-channel bench power supply."""

    def __init__(self, address: str, protocol, debug=None):
        super().__init__(address, protocol, debug=debug)
        self._state_lock = Lock()
        self._configured_voltage = 5.0
        self._current_limit = 0.5
        self._output_enabled = False
        self._load_resistance = 20.0

    def background_task(self):
        while self.background_task_running:
            sleep(0.25)

    def greet(self, message: Message) -> bool:
        self.protocol.send_response(
            message,
            {
                "module": self.address,
                "kind": "simulated_power_supply",
                "commands": ["configure_output", "enable_output", "read_output", "set_load"],
            },
        )
        return False

    def _to_float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _status(self) -> dict[str, Any]:
        with self._state_lock:
            configured_voltage = self._configured_voltage
            current_limit = self._current_limit
            output_enabled = self._output_enabled
            load_resistance = max(0.001, self._load_resistance)

        if output_enabled:
            ideal_current = configured_voltage / load_resistance
            if ideal_current > current_limit:
                measured_current = current_limit
                measured_voltage = measured_current * load_resistance
            else:
                measured_current = ideal_current
                measured_voltage = configured_voltage
        else:
            measured_current = 0.0
            measured_voltage = 0.0

        return {
            "output_enabled": output_enabled,
            "configured_voltage": round(configured_voltage, 4),
            "current_limit": round(current_limit, 4),
            "load_resistance": round(load_resistance, 4),
            "voltage": round(measured_voltage, 4),
            "current": round(measured_current, 4),
            "power": round(measured_voltage * measured_current, 4),
        }

    def configure_output(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        with self._state_lock:
            self._configured_voltage = max(0.0, self._to_float(payload.get("voltage"), self._configured_voltage))
            self._current_limit = max(0.0, self._to_float(payload.get("current_limit"), self._current_limit))

        if message.source is not None:
            self.protocol.send_response(message, {"ok": True, **self._status()})
        return False

    def enable_output(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        enabled = bool(payload.get("enabled", False))
        with self._state_lock:
            self._output_enabled = enabled

        if message.source is not None:
            self.protocol.send_response(message, {"ok": True, **self._status()})
        return False

    def read_output(self, message: Message) -> bool:
        self.protocol.send_response(message, self._status())
        return False

    def set_load(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        with self._state_lock:
            self._load_resistance = max(0.001, self._to_float(payload.get("load_resistance"), self._load_resistance))

        if message.source is not None:
            self.protocol.send_response(message, {"ok": True, **self._status()})
        return False


PowerSupply.register("simulated", SimulatedPowerSupply)
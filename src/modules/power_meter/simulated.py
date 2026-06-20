"""Simulated implementation of PowerMeter for development and testing."""

import random
from threading import Lock
from time import sleep
from typing import Any

from pyqmh import Message

from .base import BasePowerMeter
from .factory import PowerMeter


class SimulatedPowerMeter(BasePowerMeter):
    """Simple simulated power meter that reads from the power_supply module."""

    def __init__(self, address: str, protocol, debug=None):
        super().__init__(address, protocol, debug=debug)
        self._state_lock = Lock()
        self._rng = random.Random()
        self._noise_percent = 0.5
        self._last_measurement = {
            "channel": 1,
            "voltage": 0.0,
            "current": 0.0,
            "power": 0.0,
            "source": "idle",
        }

    def background_task(self):
        while self.background_task_running:
            sleep(0.25)

    def greet(self, message: Message) -> bool:
        self.protocol.send_response(
            message,
            {
                "module": self.address,
                "kind": "simulated_power_meter",
                "commands": ["measure", "set_noise", "read_status"],
            },
        )
        return False

    def _to_float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _to_int(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _with_noise(self, value: float, noise_fraction: float) -> float:
        spread = abs(value) * noise_fraction
        if spread == 0.0:
            spread = noise_fraction * 0.02
        return value + self._rng.uniform(-spread, spread)

    def _status(self) -> dict[str, Any]:
        with self._state_lock:
            last = dict(self._last_measurement)
            noise_percent = self._noise_percent
        return {
            "noise_percent": round(noise_percent, 4),
            "last_measurement": last,
        }

    def measure(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        channel = max(1, self._to_int(payload.get("channel"), 1))

        source = "power_supply"
        try:
            supply_state = self.protocol.send_request(
                "power_supply",
                "read_output",
                payload={"channel": channel},
                timeout=1.0,
            )
        except TimeoutError:
            supply_state = {}
            source = "fallback_timeout"
        except Exception:
            supply_state = {}
            source = "fallback_error"

        base_voltage = self._to_float(getattr(supply_state, "get", lambda *_: 0.0)("voltage", 0.0), 0.0)
        base_current = self._to_float(getattr(supply_state, "get", lambda *_: 0.0)("current", 0.0), 0.0)

        with self._state_lock:
            noise_fraction = max(0.0, self._noise_percent) / 100.0

        measured_voltage = self._with_noise(base_voltage, noise_fraction)
        measured_current = self._with_noise(base_current, noise_fraction)
        measured_power = measured_voltage * measured_current

        response = {
            "channel": channel,
            "voltage": round(measured_voltage, 4),
            "current": round(measured_current, 4),
            "power": round(measured_power, 4),
            "source": source,
        }

        with self._state_lock:
            self._last_measurement = dict(response)

        self.protocol.send_response(message, response)
        return False

    def set_noise(self, message: Message) -> bool:
        payload = self._payload_as_dict(message)
        with self._state_lock:
            self._noise_percent = max(0.0, self._to_float(payload.get("noise_percent"), self._noise_percent))

        if message.source is not None:
            self.protocol.send_response(message, {"ok": True, **self._status()})
        return False

    def read_status(self, message: Message) -> bool:
        self.protocol.send_response(message, self._status())
        return False


PowerMeter.register("simulated", SimulatedPowerMeter)
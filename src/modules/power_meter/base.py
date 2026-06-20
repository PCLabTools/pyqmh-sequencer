"""
file: base.py
description: Base implementation contract for PowerMeter modules.
author: Larry
"""

import logging
from typing import Any, Optional
from abc import ABC, abstractmethod
from pyqmh import Message, Protocol, Module


class BasePowerMeter(Module, ABC):
    """Abstract base class for PowerMeter implementations."""

    def __init__(self, address: str, protocol: Protocol, debug: Optional[bool] = None):
        """Initialises the factory module.

        Args:
            address (str): Unique address for the module.
            protocol (Protocol): The protocol instance.
            debug (bool, optional): Debug flag. Defaults to None.
        """
        super().__init__(address, protocol, debug=debug)
        self.logger = logging.getLogger("pyqmh.module").getChild(self.address)
        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)

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
        if message.command == "measure":
            return self.measure(message)
        if message.command == "set_noise":
            return self.set_noise(message)
        if message.command == "read_status":
            return self.read_status(message)
        return super().handle_message(message)

    def _payload_as_dict(self, message: Message) -> dict[str, Any]:
        payload = getattr(message, "payload", None)
        return payload if isinstance(payload, dict) else {}

    @abstractmethod
    def background_task(self):
        """Background task - must be implemented by each factory implementation."""
        raise NotImplementedError("background_task must be implemented by subclasses")

    @abstractmethod
    def greet(self, message: Message) -> bool:
        """Handle the greet message - must be implemented by each factory implementation.

        Args:
            message (Message): Incoming message.

        Returns:
            bool: False to continue running.
        """
        raise NotImplementedError("greet must be implemented by subclasses")

    @abstractmethod
    def measure(self, message: Message) -> bool:
        """Return one measurement sample for requested channel."""
        raise NotImplementedError("measure must be implemented by subclasses")

    @abstractmethod
    def set_noise(self, message: Message) -> bool:
        """Set relative measurement noise level from payload field noise_percent."""
        raise NotImplementedError("set_noise must be implemented by subclasses")

    @abstractmethod
    def read_status(self, message: Message) -> bool:
        """Return current meter status and most recent measurement."""
        raise NotImplementedError("read_status must be implemented by subclasses")
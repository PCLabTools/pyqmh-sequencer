"""
file: base.py
description: Base implementation contract for PowerSupply modules.
author: Larry
"""

import logging
from typing import Any, Optional
from abc import ABC, abstractmethod
from pyqmh import Message, Protocol, Module


class BasePowerSupply(Module, ABC):
    """Abstract base class for PowerSupply implementations."""

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
        if message.command == "configure_output":
            return self.configure_output(message)
        if message.command == "enable_output":
            return self.enable_output(message)
        if message.command == "read_output":
            return self.read_output(message)
        if message.command == "set_load":
            return self.set_load(message)
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
    def configure_output(self, message: Message) -> bool:
        """Apply output setpoints from payload fields voltage and current_limit."""
        raise NotImplementedError("configure_output must be implemented by subclasses")

    @abstractmethod
    def enable_output(self, message: Message) -> bool:
        """Enable or disable the power supply output from payload field enabled."""
        raise NotImplementedError("enable_output must be implemented by subclasses")

    @abstractmethod
    def read_output(self, message: Message) -> bool:
        """Return current output status and measurements."""
        raise NotImplementedError("read_output must be implemented by subclasses")

    @abstractmethod
    def set_load(self, message: Message) -> bool:
        """Update simulated load in ohms from payload field load_resistance."""
        raise NotImplementedError("set_load must be implemented by subclasses")
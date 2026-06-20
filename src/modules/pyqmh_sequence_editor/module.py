"""
file: module.py
description: pyqmh Sequence Editor for creating, editing and managing pyqmh sequence files
author: Larry
"""

from time import sleep
from typing import Optional
from pyqmh import Message, Protocol, Module


class PyqmhSequenceEditor(Module):
    """
    PyqmhSequenceEditor is a module that extends the base Module class from the Queued Message Handling (QMH) Framework. It provides custom message handling and background task functionality.
    """

    def __init__(self, address: str, protocol: Protocol, debug: Optional[bool] = None):
        """Initialises the module and sets up the protocol.

        Args:
            address (str): The address of the module.
            protocol (Protocol): The protocol instance.
            debug (Optional[bool]): If provided, overrides logger level for this module.
        """
        super().__init__(address, protocol, debug=debug)

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
        return super().handle_message(message)

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
        self.protocol.send_response(message, {"response": "Hello, World!"})
        return False
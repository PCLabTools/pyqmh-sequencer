"""
file: pyqmh_sequence_engine/app.py
description: pyqmh Sequence Engine designed to execute sequences
author: Larry
"""

import logging
import argparse
from pyqmh import Protocol, Message
from module import PyqmhSequenceEngine

class App():
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.address = "main"
        self.protocol = Protocol(self.address)
        self.logger = logging.getLogger("pyqmh.module").getChild(self.address)
        self.logger.setLevel(logging.DEBUG if self.debug else logging.INFO)

        # Register modules here
        PyqmhSequenceEngine("PyqmhSequenceEngine", self.protocol, debug=self.debug)

    def __del__(self):
        """Clean up the main module by deleting the protocol instance.
        """
        del self.protocol

    def run(self):
        """Run the main application loop and handles application shutdown.
        """
        self.logger.debug("Starting main application loop.")

        # Perform any actions needed before entering the main loop, such as initializing modules or setting up resources.

        print(f"\033[92mMain application loop has started. Press Ctrl+C to exit.\033[0m")

        while True:
            try:
                message = self.protocol.receive_message(self.address, timeout=0.2)
                if self.handle_message(message):
                    break
            except TimeoutError:
                continue
            except KeyboardInterrupt:
                self.logger.debug("Keyboard interrupt received. Shutting down.")
                self.protocol.broadcast_message("shutdown")
                break

    def handle_message(self, message: Message) -> bool:
        """Handle incoming messages.

        Args:
            message: The message to handle.

        Returns:
            bool: True if the message was handled successfully, False otherwise.
        """
        self.logger.debug(f"Handling message: {message}")
        if message.command == "shutdown":
            self.logger.debug("Received shutdown command. Shutting down.")
            self.protocol.broadcast_message("shutdown")
            try:
                self.protocol.receive_message(self.address, timeout=5)  # Wait for acknowledgments
            except TimeoutError:
                self.logger.debug("Timeout occurred while waiting for acknowledgments.")
            return True
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the pyqmh app.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(name)s - %(levelname)s - %(message)s",
    )
    app = App(debug=args.debug)
    app.run()
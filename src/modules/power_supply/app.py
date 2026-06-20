"""
file: power_supply/app.py
description: Power Supply module designed to control connected power supplies that communicate using the VISA protocol
author: Larry
"""

import logging
import argparse
import os
import sys
from pyqmh import Protocol, Message

if __package__ in (None, ""):
    # Support running this file directly: python src/modules/power_supply/app.py
    src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    from modules.power_supply.factory import PowerSupply
    from modules.power_supply.www import ModuleWebGui
else:
    from .factory import PowerSupply
    from .www import ModuleWebGui

class App():
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.address = "main"
        self.protocol = Protocol(self.address)
        self.logger = logging.getLogger("pyqmh.module").getChild(self.address)
        self.logger.setLevel(logging.DEBUG if self.debug else logging.INFO)

        # Register modules here
        PowerSupply("power_supply", self.protocol, debug=self.debug)

        self._web_gui = ModuleWebGui(
            logger=self.logger,
            protocol=self.protocol,
            module_folder_name="power_supply",
        )

    def __del__(self):
        """Clean up the main module by deleting the protocol instance.
        """
        del self.protocol

    def run(self):
        """Run the main application loop and handles application shutdown.
        """
        self.logger.debug("Starting main application loop.")
        self._web_gui.start()

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
    # app.run()
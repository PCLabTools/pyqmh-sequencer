"""
file: factory.py
description: Factory module for creating PowerSupply instances with swappable implementations.
author: Larry
"""

from typing import Optional
from pyqmh import Protocol

from .base import BasePowerSupply


class PowerSupply:
    """Factory for creating PowerSupply instances with swappable implementations at runtime.

    Raises:
        ValueError: When an invalid implementation type is specified.

    Returns:
        BasePowerSupply: An instance of the factory module based on the specified implementation type.
    """

    _implementations: dict[str, type[BasePowerSupply]] = {}

    @classmethod
    def register(cls, implementation: str, module_class: type[BasePowerSupply]):
        """Registers a factory implementation.

        Args:
            implementation (str): The name of the implementation.
            module_class (type[BasePowerSupply]): The class to register.
        """
        cls._implementations[implementation.lower()] = module_class

    @classmethod
    def create(
        cls,
        address: str,
        protocol: Protocol,
        debug: Optional[bool] = None,
        implementation_type: str = "simulated",
    ) -> BasePowerSupply:
        """Creates a factory module instance based on implementation type.

        Args:
            address (str): Unique address for the module.
            protocol (Protocol): The protocol instance.
            debug (bool, optional): Debug flag. Defaults to None.
            implementation_type (str, optional): Implementation to create. Defaults to "simulated".

        Returns:
            BasePowerSupply: The created module instance.

        Raises:
            ValueError: If the specified implementation type is not registered.
        """
        implementation_type = implementation_type.lower()
        if implementation_type not in cls._implementations:
            raise ValueError(f"PowerSupply: No factory implementation registered for type '{implementation_type}'")
        return cls._implementations[implementation_type](address, protocol, debug)

    def __new__(
        cls,
        address: str,
        protocol: Protocol,
        debug: Optional[bool] = None,
        implementation_type: str = "simulated",
    ) -> BasePowerSupply:
        return cls.create(address, protocol, debug, implementation_type)


# Import implementations to register them.
from . import simulated  # noqa: E402,F401
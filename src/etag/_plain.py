"""Read caller values as exact built-in types and check option types.

Types are judged by the real type of a value (``type(value)``), never by ``isinstance``,
which believes a ``__class__`` property, and subclasses are read through the base class.
"""

from __future__ import annotations

from typing import cast


def type_name(value: object) -> str:
    """The type name of a value for an error message, at most 40 characters."""
    # The name slot of the type itself: a metaclass property cannot replace or inflate it.
    name: str = type.__dict__["__name__"].__get__(type(value))
    return str.__getitem__(name, slice(0, 40))


def as_text(value: object) -> str | None:
    """An exact ``str`` copy of a str or a subclass of it, or ``None`` for anything else."""
    if not issubclass(type(value), str):
        return None
    return str.__str__(cast(str, value))


def as_octets(value: object) -> bytes | bytearray | None:
    """The octets of bytes, a bytearray or a subclass, or ``None`` for anything else.

    A subclass is copied through the base class, so an overridden ``__buffer__`` (Python
    3.12 and later) or ``decode`` cannot change what is read.
    """
    kind = type(value)
    if kind is bytes or kind is bytearray:
        return cast("bytes | bytearray", value)
    if issubclass(kind, bytes):
        return bytes.__getitem__(cast(bytes, value), slice(None))
    if issubclass(kind, bytearray):
        return bytearray.__getitem__(cast(bytearray, value), slice(None))
    return None


def check_flag(name: str, value: object) -> bool:
    """Return an option that is a real bool, or raise TypeError."""
    # bool cannot be subclassed, so the exact type is the only test a __class__ cannot fool.
    if type(value) is not bool:
        raise TypeError(f"{name} must be a bool, not {type_name(value)}")
    return value

"""Read caller values as exact built-in types and check option types."""

from __future__ import annotations


def type_name(value: object) -> str:
    """The type name of a value for an error message, at most 40 characters."""
    # The name slot of the type itself: a metaclass property cannot replace or inflate it.
    name: str = type.__dict__["__name__"].__get__(type(value))
    return str.__getitem__(name, slice(0, 40))


def text(value: str) -> str:
    """An exact ``str`` copy, so a subclass cannot steer what is read through its methods."""
    return str.__str__(value)


def octets(value: bytes | bytearray) -> str:
    """Read bytes as Latin-1, where every octet maps to the code point of the same value."""
    if isinstance(value, bytes):
        return bytes.decode(value, "latin-1")
    return bytearray.decode(value, "latin-1")


def check_flag(name: str, value: object) -> None:
    """Raise TypeError unless an option is a real bool."""
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a bool, not {type_name(value)}")

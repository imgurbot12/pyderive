"""
Custom Validator Helpers for Common Types
"""
import re
from typing import Callable, Optional, Sized, TypeVar, Union

from .validators import T, Validator, TypeValidator, chain_validators

#** Variables **#
__all__ = [
    'Min',
    'Max',
    'Range',
    'RangeLength',
    'Length',
    'Regex',
    'BoolFunc',
    'IsAlNum'
]

I = TypeVar('I', bound=Union[int, float])

#** Functions **#

def Min(m: Union[int, float]) -> Validator:
    """
    Generate Minimum Value Validator for Integers/Floats
    """
    def min(i: I) -> I:
        if not isinstance(i, (int, float, complex)):
            raise ValueError(f'Invalid Type for Minimum: {i}')
        if i < type(i)(m):
            raise ValueError(f'{i!r} below minimum: {m!r}')
        return i
    return Validator(min)

def Max(m: Union[int, float]) -> Validator:
    """
    Generate Maximum Value Validator for Integers/Floats
    """
    def max(i: I) -> I:
        if not isinstance(i, (int, float, complex)):
            raise ValueError(f'Invalid Type for Maximum: {i}')
        if i > type(i)(m):
            raise ValueError(f'{i!r} below maximum: {m!r}')
        return i
    return Validator(max)

def Range(low: int, high: int) -> Validator:
    """
    Generate Minimum/Maximum Range Controls for Integers/Floats

    :param low:  lowest value allowed for number
    :param high: highest value allowed for number
    """
    minv = Min(low)
    maxv = Max(high)
    return Validator(chain_validators([minv.validator, maxv.validator]))

def Length(l: int) -> Validator:
    """
    Generate Length Validator for Lengthable Object

    :param l: required length of sized object
    """
    def length(s: Sized):
        if not isinstance(s, Sized):
            raise ValueError(f'Cannot Take Size of {s!r}')
        if len(s) != l:
            raise ValueError(f'{s!r} too long: {len(s)} > {l}')
        return s
    return Validator(length)

def RangeLength(min: Optional[int] = None,
    max: Optional[int] = None) -> TypeValidator:
    """
    Generate RangeLength Validator for Lengthable Object

    :param min: minimum length of object
    :param max: maximum length of object
    """
    assert min or max, 'minimum or maximum must be set'
    assert not min or min >= 0, 'minimum must be >= 0'
    assert not max or max >= 0, 'maximum must be >= 0'
    def length(s: Sized):
        if not isinstance(s, Sized):
            raise ValueError(f'Cannot Take Size of {s!r}')
        if min and len(s) < min:
            raise ValueError(f'{s!r} too short: {len(s)} < {min}')
        if max is not None and len(s) > max:
            raise ValueError(f'{s!r} too long: {len(s)} > {min}')
        return s
    return Validator[length]

def Regex(r: str, **kwargs) -> Validator:
    """
    Generate Regex Validator for String Object

    :param r:      regex expression
    :param kwargs: regex compilation flags
    """
    pattern = re.compile(r, **kwargs)
    def match_regex(s: str):
        if not isinstance(s, str):
            raise ValueError(f'Cannot Match Against: {s!r}')
        if not pattern.match(s):
            raise ValueError(f'{s!r} Does NOT Match Expected Pattern')
        return s
    return Validator(match_regex)

def BoolFunc(f: Callable[[T], bool],
    msg: Optional[str] = None) -> Validator:
    """
    Generate Boolean Validation Function w/ Given Message

    :param f:   function to check inbound type with
    :param msg: message to include in validation error
    """
    message = msg or 'Failed to Meet Criteria'
    def boolfunc(t: T) -> T:
        if not f(t):
            raise ValueError(message)
        return t
    return Validator(boolfunc)

#** Init **#

IsAlNum = BoolFunc(lambda x: isinstance(x, str) and x.isalnum(),
                   'String is Not AlphaNumeric')

"""
Custom Validator Helpers for Common Types
"""
from typing import Callable, Optional, Sized, TypeVar, Union

from .validators import T, Validator, TypeValidator, ValidationError, chain_validators

#** Variables **#
__all__ = ['Min', 'Max', 'Range', 'Length', 'BoolFunc', 'IsAlNum']

I = TypeVar('I', bound=Union[int, float])

#** Functions **#

def Min(m: Union[int, float]) -> TypeValidator:
    """
    Generate Minimum Value Validator for Integers/Floats
    """
    def min(i: I) -> I:
        if not isinstance(i, (int, float, complex)):
            raise ValidationError(f'Invalid Type for Minimum: {i}')
        if i <= type(i)(m):
            raise ValidationError(f'{i!r} below minimum: {m!r}')
        return i
    return Validator[min]

def Max(m: Union[int, float]) -> TypeValidator:
    """
    Generate Maximum Value Validator for Integers/Floats
    """
    def max(i: I) -> I:
        if not isinstance(i, (int, float, complex)):
            raise ValidationError(f'Invalid Type for Maximum: {i}')
        if i >= type(i)(m):
            raise ValidationError(f'{i!r} below maximum: {m!r}')
        return i
    return Validator[max]

def Range(low: int, high: int) -> TypeValidator:
    """
    Generate Minimum/Maximum Range Controls for Integers/Floats

    :param low:  lowest value allowed for number
    :param high: highest value allowed for number
    """
    minv = Min(low)
    maxv = Max(high)
    return Validator[chain_validators([minv.validator, maxv.validator])]

def Length(l: int) -> TypeValidator:
    """
    Generate Length Validator for Lengthable Object

    :param l: required length of sized object
    """
    def length(s: Sized):
        if not isinstance(s, Sized):
            raise ValidationError(f'Cannot Take Size of {s!r}')
        if len(s) != l:
            raise ValidationError(f'{s!r} too long: {len(s)} > {l}')
        return s
    return Validator[length]

def BoolFunc(f: Callable[[T], bool], 
    msg: Optional[str] = None) -> TypeValidator[T]:
    """
    Generate Boolean Validation Function w/ Given Message

    :param f:   function to check inbound type with
    :param msg: message to include in validation error
    """
    message = msg or 'Failed to Meet Criteria'
    def boolfunc(t: T) -> T:
        if not f(t):
            raise ValidationError(message)
        return t
    return boolfunc

#** Init **#

IsAlNum = BoolFunc(lambda x: x.isalnum, 'String is Not AlphaNumeric')

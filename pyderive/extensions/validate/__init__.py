"""
PyDantic Inspired Pyderive Validator Extensions
"""
from ipaddress import *
from typing import Any, Mapping, Sequence, Set, Type, Union, Callable, overload
from typing_extensions import Annotated

from .validators import *

from ...abc import T, has_default
from ...compile import assign_func, create_init
from ...dataclasses import POST_INIT, PARAMS_ATTR, FIELD_ATTR, is_dataclass

#** Variables **#
__all__ = [
    'IPv4',
    'IPv6',
    'IPvAnyAddress',
    'IPvAnyNetwork',
    'IPvAnyInterface',

    'validate',

    'Validator',
    'PreValidator',
    'PostValidator',
]

IPv4 = Annotated[Union[IPv4Address, str, bytes], PreValidator[IPv4Address]]
IPv6 = Annotated[Union[IPv6Address, str, bytes], PreValidator[IPv6Address]]

IPvAnyAddress = Annotated[Union[IPv4Address, IPv6Address, str, bytes], PreValidator[ip_address]]
IPvAnyNetwork = Annotated[Union[IPv4Network, IPv6Network, str, bytes], PreValidator[ip_network]]
IPvAnyInterface = Annotated[Union[IPv4Interface, IPv6Interface, str, bytes], PreValidator[ip_interface]]

#** Functions **#

@overload
def validate(cls: None = None, typecast: bool = False) -> Callable[[T], T]:
    ...

@overload
def validate(cls: T, typecast: bool = False) -> T:
    ...

def validate(cls = None, typecast: bool = False):
    """
    validation decorator to use on top of an existing dataclass

    :param cls:      dataclass instance
    :param typecast: enable typecasting during validation
    :return:         same dataclass instance now validation wrapped
    """
    def wrapper(cls: T) -> T:
        if not is_dataclass(cls):
            raise TypeError('Cannot validate non-dataclass instance!')
        # append validators to the field definitions
        fields = getattr(cls, FIELD_ATTR)
        params = getattr(cls, PARAMS_ATTR)
        for field in fields:
            field.validator = field.validator or field_validator(field, typecast)
        # regenerate init to include new validators
        post_init = hasattr(cls, POST_INIT)
        func = create_init(fields, params.kw_only, post_init, params.frozen)
        assign_func(cls, func, overwrite=True)
        return cls
    return wrapper if cls is None else wrapper(cls)

def _parse_object(anno: Type, value: Any, **kwargs) -> Any:
    """"""
    if is_dataclass(anno):
        if isinstance(value, (set, Sequence)) and not isinstance(value, str):
            return from_sequence(anno, value, **kwargs)
        elif isinstance(value, Mapping):
            return from_mapping(anno, value, **kwargs)
    return value

def from_sequence(cls: Type[T], values: Union[Sequence, Set], **kwargs) -> T:
    """
    parse random sequence into a valid dataclasss object
    """
    if not is_dataclass(cls) and not isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    # check range of parameters
    fields = getattr(cls, FIELD_ATTR)
    if len(values) > len(fields):
        raise TypeError(f'{cls.__name__}: sequence contains too many values.')
    # limit number of fields to required components
    if len(values) < len(fields):
        required = [f for f in fields if has_default(f)]
        optional = [(n,f) for n,f in enumerate(fields, 0) if not has_default(f)]
        while len(required) < len(values):
            pos, field = optional.pop(0)
            required.insert(pos, field)
        fields = required
    # iterate values and try to match to annotations
    kwargs = {}
    for field, value in zip(fields, values):
        kwargs[field.name] = _parse_object(field.anno, value, **kwargs)
    return cls(**kwargs)

def from_mapping(cls: Type[T], 
    values: Mapping, *, allow_unknown: bool = False, **kwargs) -> T:
    """
    parse random mapping into a valid dataclass object
    """
    if not is_dataclass(cls) and not isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    kwargs.setdefault('allow_unknown', allow_unknown)
    # parse key/value into kwargs
    kwargs = {}
    fields = getattr(cls, FIELD_ATTR)
    fdict  = {f.name:f for f in fields}
    for key, value in values.items():
        # handle unexpected keys
        if key not in fdict:
            if allow_unknown:
                continue
            raise KeyError(f'Unknown Key: {key!r}')
        # translate value based on annotation
        field       = fdict[key]
        kwargs[key] = _parse_object(field.anno, value, **kwargs)
    return cls(**kwargs)

def from_object(cls: Type[T], values: Any, **kwargs) -> T:
    """
    parse random python object construction into valid dataclass instance
    """
    if not is_dataclass(cls) and not isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    if isinstance(values, (set, Sequence)) and not isinstance(values, str):
        return from_sequence(cls, values, **kwargs)
    elif isinstance(values, Mapping):
        return from_mapping(cls, values, **kwargs)
    raise TypeError(f'Cannot deconstruct: {values!r}')

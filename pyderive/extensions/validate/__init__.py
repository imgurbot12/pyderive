"""
PyDantic Inspired Pyderive Validator Extensions
"""
from typing import Any, Mapping, Sequence, Set, Type, Union, overload
from typing_extensions import Self, dataclass_transform
from warnings import warn

from .types import *
from .validators import *

from ...abc import T, TypeT, DataFunc, has_default
from ...compile import assign_func, create_init, gen_slots
from ...dataclasses import POST_INIT, PARAMS_ATTR, FIELD_ATTR, fields, is_dataclass, dataclass

#** Variables **#
__all__ = [
    'IPv4',
    'IPv6',
    'IPvAnyAddress',
    'IPvAnyNetwork',
    'IPvAnyInterface',
    'URL',
    'Domain',
    'Host',
    'Port',
    'ExistingFile',
    'Datetime',
    'Timedelta',

    'has_validation',
    'validate',
    'from_object',
    'from_mapping',
    'from_sequence',

    'TypeValidator',
    'register_validator',

    'BaseModel',
    'Validator',
    'PreValidator',
    'PostValidator',
]

#: attribute to store dataclass validation information
VALIDATE_ATTR = '__pyderive_validate__'

#** Functions **#

def has_validation(cls) -> bool:
    """
    return true if object has validation enabled

    :param cls: dataclass object
    :return:    true if object has validation else false
    """
    return is_dataclass(cls) and hasattr(cls, VALIDATE_ATTR)

@overload
def validate(cls: None = None, typecast: bool = False, **kwargs) -> DataFunc:
    ...

@overload
def validate(cls: TypeT, typecast: bool = False, **kwargs) -> TypeT:
    ...

@dataclass_transform()
def validate(cls = None, typecast: bool = False, **kwargs):
    """
    validation decorator to use on top of an existing dataclass

    :param cls:      dataclass instance
    :param typecast: enable typecasting during validation
    :param kwargs:   kwargs to apply when generating dataclass
    :return:         same dataclass instance now validation wrapped
    """
    def wrapper(cls: TypeT) -> TypeT:
        # convert to dataclass using kwargs if not already a dataclass
        if kwargs and is_dataclass(cls):
            raise TypeError(f'{cls} is already a dataclass!')
        if not is_dataclass(cls):
            kwargs.setdefault('slots', True)
            cls = dataclass(cls, init=False, **kwargs)
        # append validators to the field definitions
        fields = getattr(cls, FIELD_ATTR)
        params = getattr(cls, PARAMS_ATTR)
        for f in fields:
            f.validator = f.validator or field_validator(f, typecast)
            # recursively configure dataclass annotations
            if is_dataclass(f.anno) and not hasattr(f.anno, VALIDATE_ATTR):
                f.anno = validate(f.anno, typecast)
        # regenerate init to include new validators
        post_init = hasattr(cls, POST_INIT)
        func = create_init(fields, params.kw_only, post_init, params.frozen)
        assign_func(cls, func, overwrite=True)
        # set validate-attr and preserve configuration settings
        setattr(cls, VALIDATE_ATTR, ValidateParams(typecast))        
        return cls
    return wrapper if cls is None else wrapper(cls)

def _parse_object(anno: Type, value: Any, **kwargs) -> Any:
    """recursively parse dataclass annotation"""
    if is_dataclass(anno):
        if is_sequence(value):
            return from_sequence(anno, value, **kwargs)
        elif isinstance(value, Mapping):
            return from_mapping(anno, value, **kwargs)
    return value

def from_sequence(cls: Type[T], values: Union[Sequence, Set], **kwargs) -> T:
    """
    parse sequence into a valid dataclasss object

    :param cls:    validation capable dataclass object
    :param values: sequence to parse into valid dataclass object
    :param kwargs: additional arguments to pass to recursive evaluation
    :return:       parsed dataclass object
    """
    if not is_dataclass(cls) and not isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    if not has_validation(cls):
        warn(f'Dataclass: {cls.__name__} has no type validation.')
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
    attrs = {}
    for field, value in zip(fields, values):
        attrs[field.name] = _parse_object(field.anno, value, **kwargs)
    return cls(**attrs)

def from_mapping(cls: Type[T], 
    values: Mapping, *, allow_unknown: bool = False, **kwargs) -> T:
    """
    parse mapping into a valid dataclass object

    :param cls:           validation capable dataclass object
    :param values:        sequence to parse into valid dataclass object
    :param allow_unknown: allow for unknown and invalid keys during dict parsing
    :param kwargs:        additional arguments to pass to recursive evaluation
    :return:              parsed dataclass object
    """
    if not is_dataclass(cls) and not isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    if not has_validation(cls):
        warn(f'Dataclass: {cls.__name__} has no type validation.')
    # parse key/value into kwargs
    kwargs.setdefault('allow_unknown', allow_unknown)
    fields = getattr(cls, FIELD_ATTR)
    fdict  = {f.name:f for f in fields}
    attrs  = {}
    for key, value in values.items():
        # handle unexpected keys
        if key not in fdict:
            if allow_unknown:
                continue
            raise KeyError(f'Unknown Key: {key!r}')
        # translate value based on annotation
        field       = fdict[key]
        attrs[key] = _parse_object(field.anno, value, **kwargs)
    return cls(**attrs)

def from_object(cls: Type[T], value: Any, **kwargs) -> T:
    """
    parse an object into a valid dataclass instance

    :param cls:    validation capable dataclass object
    :param values: object into valid dataclass object
    :param kwargs: additional arguments to pass to recursive evaluation
    :return:       parsed dataclass object
    """
    if not is_dataclass(cls) and not isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    if is_sequence(value):
        return from_sequence(cls, value, **kwargs)
    elif isinstance(value, Mapping):
        return from_mapping(cls, value, **kwargs)
    raise TypeError(f'Cannot deconstruct: {value!r}')

#** Classes **#

@dataclass(slots=True)
class ValidateParams:
    typecast: bool = False

@dataclass_transform()
class BaseModel:
    """
    PyDantic Inspirted Validation Model MetaClass
    """

    def __init_subclass__(cls, 
        typecast: bool = False, slots: bool = True, **kwargs):
        """
        :param typecast: allow typecasting of input values
        :param slots:    add slots to the model object
        :param kwargs:   extra arguments to pass to dataclass generation
        """
        dataclass(cls, slots=False, **kwargs)
        validate(cls, typecast)
        if slots:
            setattr(cls, '__slots__', gen_slots(cls, fields(cls)))
 
    def validate(self):
        """run ad-hoc validation against current model values"""
        for field in fields(self):
            value = getattr(self, field.name)
            if field.validator is not None:
                field.validator(self, field, value)

    @classmethod
    def parse_obj(cls, value: Any, **kwargs) -> Self:
        """
        parse value into valid dataclass object

        :param value:  object to parse into dataclass
        :param kwargs: additional arguments to pass to parser
        :return:       model instance
        """
        return from_object(cls, value, **kwargs)

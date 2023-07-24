"""
PyDantic Inspired Pyderive Validator Extensions
"""
from typing import Any, overload
from typing_extensions import Self, dataclass_transform

from .types import *
from .validators import *

from ..serde import from_object
from ...abc import TypeT, DataFunc
from ...compile import assign_func, create_init, gen_slots
from ...dataclasses import POST_INIT, PARAMS_ATTR, FIELD_ATTR
from ...dataclasses import *

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
    'Loglevel',
    'Datetime',
    'Timedelta',

    'has_validation',
    'validate',

    'TypeValidator',
    'register_validator',

    'BaseModel',
    'Validator',
    'PreValidator',
    'PostValidator',
    'ValidationError',
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
            cls = dataclass(cls, init=False, **kwargs) #type: ignore
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

"""
PyDantic Inspired Pyderive Validator Extensions
"""
from abc import abstractmethod
from typing import Any, Iterator, overload
from typing_extensions import Self, dataclass_transform

from .types import *
from .generic import *
from .helpers import *
from .validators import *

from ..serde import from_object
from ...abc import TypeT, DataFunc, has_default
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
    'Domain',
    'Email',
    'UUID',
    'MacAddr',
    'PhoneNumber',
    'Bytes',
    'HexBytes',
    'URL',
    'Host',
    'Port',
    'ExistingFile',
    'Loglevel',
    'Datetime',
    'Timedelta',

    'Min',
    'Max',
    'Range',
    'RangeLength',
    'Length',
    'Regex',
    'BoolFunc',
    'IsAlNum',

    'has_validation',
    'validate',

    'TypeValidator',
    'register_validator',

    'BaseModel',
    'BaseTuple',
    'Validator',
    'PreValidator',
    'PostValidator',
    'ValidationError',
    'FieldValidationError',
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
def validate(cls: None = None, **kwargs) -> DataFunc:
    ...

@overload
def validate(cls: TypeT, **kwargs) -> TypeT:
    ...

@dataclass_transform()
def validate(cls = None, *,
    recurse: bool = False, typecast: bool = False, **kwargs):
    """
    validation decorator to use on top of an existing dataclass

    :param cls:      dataclass instance
    :param recurse:  allow recusive validation of dataclasses
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
        # update generics if present in dataclass
        if has_generics(cls):
            update_generics(cls)
            setattr(cls, '__class_getitem__', generic_getitem)
        # retrieve previous validate-params if they exist
        nparams   = ValidateParams(typecast)
        vparams   = getattr(cls, VALIDATE_ATTR, None)
        different = vparams and vparams != nparams
        # append validators to the field definitions
        fields = getattr(cls, FIELD_ATTR)
        params = getattr(cls, PARAMS_ATTR)
        for f in fields:
            # set empty default values to MISSING for validation errors
            if not has_default(f):
                f.default_factory = lambda: MISSING
            # update validators if params have changed or were never assigned
            if different and f.validator and is_autogen(f.validator):
                f.validator = None
            f.validator = f.validator or field_validator(cls, f, typecast)
            # recursively configure dataclass annotations
            sparams        = getattr(f.anno, PARAMS_ATTR, None)
            has_validation = hasattr(f.anno, VALIDATE_ATTR)
            do_validate    = recurse and sparams and sparams.init is not False
            if do_validate and not has_validation:
                f.anno = validate(f.anno, recurse=recurse, tyepcast=typecast)
        # regenerate init to include new validators
        post_init = hasattr(cls, POST_INIT)
        func = create_init(fields, params.kw_only, post_init, params.frozen)
        assign_func(cls, func, overwrite=True)
        # set validate-attr and preserve configuration settings
        setattr(cls, VALIDATE_ATTR, nparams)
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

    def __init_subclass__(cls, recurse: bool = False,
        typecast: bool = False, slots: bool = True, **kwargs):
        """
        :param recurse:  allow recusive validation of dataclasses
        :param typecast: allow typecasting of input values
        :param slots:    add slots to the model object
        :param kwargs:   extra arguments to pass to dataclass generation
        """
        # copy genrics from baseclasses
        bases = getattr(cls, BASES_ATTR, [])
        valid = [base for base in bases if hasattr(base, GENERIC_PARAMS)]
        if valid:
            setattr(cls, GENERIC_PARAMS, getattr(valid[0], GENERIC_PARAMS))
        # generate dataclass and validations
        dataclass(cls, slots=False, **kwargs)
        validate(cls, recurse=recurse, typecast=typecast)
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

class BaseTuple(BaseModel):
    """
    Expansion on BaseModel w/ builtin tuple Deconstruction
    """

    @abstractmethod
    def __iter__(self) -> Iterator[Any]:
        return NotImplemented

    def __init_subclass__(cls, iter: bool = True, **kwargs):
        super().__init_subclass__(iter=iter, **kwargs)

"""
Type/Field Validator Implementations
"""
from enum import Enum
from typing import *
from typing_extensions import Annotated, get_origin, get_args

from ..serde import is_sequence
from ...abc import FieldDef, FieldValidator

#** Variables **#
__all__ = [
    'TypeValidator',

    'is_sequence',
    'type_validator',
    'field_validator',
    'register_validator',
    
    'ValidationError',
    
    'Validator',
    'PreValidator',
    'PostValidator',
]

#: type validator / type translation function
TypeValidator = Callable[[Any], Any]

#: global type-validator registry
TYPE_VALIDATORS: Dict[Type, List[TypeValidator]] = {}

#** Functions **#

def _anno_name(anno: Type) -> str:
    """generate clean annotation name"""
    return str(anno).split('typing.', 1)[-1]

def _wrap(name: str) -> Callable[[Callable], Callable]:
    def wrapper(func: Callable) -> Callable:
        func.__name__ = f'validate_{name}'
        func.__qualname__ = func.__name__
        return func
    return wrapper

def none_validator(value: Any):
    """
    validate value is a none-type
    """
    if value is not None:
        raise ValueError(f'{value!r} is not None')

def simple_validator(cast: Type, typecast: bool) -> TypeValidator:
    """
    generate generic validation function for the specified type

    :param cast:     python type to cast value as
    :param typecast: allow typecasting if true
    :return:         type-validator that attempts typecast
    """
    name = cast.__name__
    @_wrap(name)
    def validator(value: Any) -> Any:
        if isinstance(value, cast):
            return value
        if typecast:
            try:
                return cast(value)
            except (ValueError, ValidationError):
                pass
        raise ValidationError(f'Invalid {name}: {value!r}')
    return validator

def seq_validator(outer: Type, base: Type, iv: TypeValidator, typecast: bool) -> TypeValidator:
    """
    generate generic sequence-type typecast validator for the specified type

    :param outer:    outer sequence type definition
    :param iv:       validation for inner sequence type
    :param typecast: allow typecasting when enabled
    :return:         custom sequence validation function
    """
    name = _anno_name(outer)
    @_wrap(name)
    def validator(value: Sequence[Any]):
        if (base and not typecast and not isinstance(value, base)) \
            or not is_sequence(value):
            raise ValidationError(f'Invalid {name}: {value!r}')
        values = []
        for n, item in enumerate(value, 0):
            try:
                newitem = iv(item)
                values.append(newitem)
            except Exception as e:
                raise ValidationError(f'Index {n}, {e}') from None
        return base(values)
    return validator

def map_validator(outer: Type, 
    base: Type, kv: TypeValidator, vv: TypeValidator) -> TypeValidator:
    """
    generate generic map-type typecast validator for the specified type

    :param outer: outer mapping type definition
    :param base:  base type for mapping type definition
    :param kv:    validation for inner key type
    :param vv:    validation for inner value type
    :return:      custom mapping validation function
    """
    name = _anno_name(outer)
    @_wrap(name)
    def validator(value: Mapping[Any, Any]):
        if not isinstance(value, Mapping):
            raise ValidationError(f'Invalid {name}: {value!r}')
        values = {}
        for k,v in value.items():
            newkey = kv(k)
            newval = vv(v)
            values[newkey] = newval
        return base(values)
    return validator

def tup_validator(anno: Type, validators: List[TypeValidator], 
    ellipsis: bool, typecast: bool) -> TypeValidator:
    """
    validate tuple with the following validators

    :param anno:       base annotation
    :param validators: list of validators for each field in tuple
    :param ellipsis:   if ellipsis are present in annotation
    :param typecast:   enable typecast if true
    :return:           custom tuple validator function 
    """
    name = _anno_name(anno)
    @_wrap(name)
    def validator(value: Any):
        # convert to tuple or raise error
        if not isinstance(value, tuple):
            if not typecast:
                raise ValidationError(f'Invalid {name}: {value!r}')
            value = tuple(value)
        # ensure number of min-values matches
        if len(value) < len(validators):
            raise ValidationError(f'Not enough items in tuple: {value!r}')
        # ensure number of max-values on no elipsis
        if not ellipsis and len(value) > len(validators):
            raise ValidationError(f'Too many items in tuple: {value!r}')
        # iterate and validate items in tuple
        values = []
        for item, validator in zip(value, validators):
            newitem = validator(item)
            values.append(newitem)
        # iterate remaining items if ellipsis is enabled
        if len(values) < len(value):
            validator = validators[-1]
            for item in value[len(values):]:
                newitem = validator(item)
                values.append(newitem)
        return tuple(values)
    return validator

def enum_validator(anno: Type[Enum], typecast: bool) -> TypeValidator:
    """
    generate validator for specified enum annotation

    :param anno:     enum annotation
    :param typecast: allow typecasting to enum
    :return:         generated enum validator
    """
    @_wrap(anno.__name__)
    def validator(value: Any):
        if isinstance(value, anno):
            return value
        if typecast:
            try:
                return anno[value]
            except (KeyError, ValueError, ValidationError):
                pass
            try:
                return anno(value)
            except (ValueError, ValidationError):
                pass
        raise ValidationError(f'Invalid {anno.__name__}: {value!r}')
    return validator

def union_validator(anno: Type, 
    args: Tuple[Type, ...], validators: List[TypeValidator]) -> TypeValidator:
    """
    try all validators in the given list before raising an error

    :param anno:       base annotation
    :param args:       list of union sub-annotations
    :param validators: validators to execute
    :return:           generated union validator
    """
    # parse valid simple python types from specified arguments
    # those are the only ones allowed for faster `isinstance` check
    wrapped = list(args)
    annotations = []
    while wrapped:
        anno = wrapped.pop()
        origin, subargs = get_origin(anno), get_args(anno)
        if origin is None:
            annotations.append(anno)
            continue
        elif origin is Annotated:
            wrapped.append(subargs[0])
        elif origin is Union:
            wrapped.extend(subargs)
    annotations = tuple(annotations)
    # generate valdiator object
    @_wrap(_anno_name(anno))
    def validator(value: Any):
        if isinstance(value, annotations):
            return value
        for validator in validators:
            try:
                return validator(value)
            except (ValueError, ValidationError):
                pass
        raise ValidationError(f'Invalid Value: {value!r}')
    return validator

def chain_validators(validators: List[TypeValidator]) -> TypeValidator:
    """
    chain a series of type-validators together
    
    :param validators: list of validators to run in order
    :return:           wrapper to execute the list of validators in order
    """
    def chain(value: Any):
        for validator in validators:
            value = validator(value)
        return value
    return chain

def type_validator(anno: Type, typecast: bool) -> TypeValidator:
    """
    generate a type-validator for the given annotation

    :param anno: annotation to validate for
    :return:     field validator for the given annotation
    """
    # check for standard validator types
    if anno is None or anno is type(None):
        return none_validator
    # check if type is specifically registered
    if anno in TYPE_VALIDATORS:
        return chain_validators(TYPE_VALIDATORS[anno])
    # check for `Enum` annotation
    if isinstance(anno, type) and issubclass(anno, Enum):
        return enum_validator(anno, typecast)
    # check for `Annotated` validator definitions
    origin, args = get_origin(anno), get_args(anno)
    if origin is Annotated:
        middle    = [type_validator(args[0], typecast)]
        pre, post = [], []
        for value in args[1:]:
            if isinstance(value, PreValidator):
                pre.append(value.validator)
            elif isinstance(value, PostValidator):
                post.append(value.validator)
            elif isinstance(value, Validator):
                middle.append(value.validator)
        return chain_validators([*pre, *middle, *post])
    # check for `Union` annotation
    if origin is Union:
        validators = [type_validator(arg, typecast) for arg in args]
        return union_validator(anno, args, validators)
    # check for `tuple` annotation
    if origin is tuple:
        ellipsis   = Ellipsis in args
        validators = [type_validator(arg, typecast) 
            for arg in args if arg is not Ellipsis]
        return tup_validator(anno, validators, ellipsis, typecast)
    # check for `Sequence` annotation
    if origin in (list, set, Sequence):
        base      = list if origin is Sequence else origin
        validator = type_validator(args[0], typecast)
        return seq_validator(anno, base, validator, typecast)
    # check for `Mapping` annnotation
    if origin in (dict, Mapping):
        base          = dict if origin is Mapping else origin
        key_validator = type_validator(args[0], typecast)
        val_validator = type_validator(args[1], typecast)
        return map_validator(anno, base, key_validator, val_validator)
    # attempt a simple/typecast annotation on anything else
    return simple_validator(anno, typecast)

def field_validator(field: FieldDef, typecast: bool = False) -> FieldValidator:
    """
    generate field-validator for the specified field definition

    :param field:    field to add validator for
    :param typecast: allow for typecasting when enabled
    :return:         validation function for field
    """
    validator = type_validator(field.anno, typecast)
    def field_validator(self, field: FieldDef, value: Any):
        try:
            return validator(value)
        except ValidationError as e:
            obj = self if isinstance(self, type) else type(self)
            raise ValidationError(f'{obj.__name__}.{field.name}: {e}') from None
    field_validator.__name__ = f'validate_{field.name}'
    field_validator.__qualname__ = field_validator.__name__
    return field_validator

def register_validator(anno: Type, validator: TypeValidator):
    """
    register a new type validator for the given annotation
    
    :param anno:      annotation to register type validator with
    :param validator: validator function for the specified type
    """
    global TYPE_VALIDATORS
    TYPE_VALIDATORS.setdefault(anno, [])
    TYPE_VALIDATORS[anno].append(validator)

#** Classes **#

class ValidationError(ValueError):
    """Exception Raised When Validation Fails"""
    pass

class Validator:
    """Annotated Validator Indicator"""
    __slots__ = ('validator', )
 
    def __init__(self, validator: TypeValidator):
        if not callable(validator):
            raise TypeError('Validator: {validator!r} is not callable')
        self.validator = validator

    def __class_getitem__(cls, validator: TypeValidator):
        return cls(validator)

class PreValidator(Validator):
    """Pre Typecast Validator Indicator"""
    pass

class PostValidator(Validator):
    """Post Typecast Validator Indicator"""
    pass

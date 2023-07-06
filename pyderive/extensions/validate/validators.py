"""
Type/Field Validator Implementations
"""
from typing import Callable, List, Mapping, Tuple, Type, Any, Sequence, Union
from typing_extensions import Annotated, get_origin, get_args

from ...abc import FieldDef, FieldValidator

#** Variables **#
__all__ = [
    'TypeValidator',

    'type_validator',
    'field_validator',
    
    'ValidationError',
    
    'Validator',
    'PreValidator',
    'PostValidator',
]

#: type validator / type translation function
TypeValidator = Callable[[Any], Any]

#** Functions **#

def _anno_name(anno: Type) -> str:
    """generate clean annotation name"""
    return str(anno).split('typing.', 1)[-1]

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
    def validator(value: Any) -> Any:
        if isinstance(value, cast):
            return value
        if typecast:
            try:
                return cast(value)
            except Exception:
                pass
        raise ValidationError(f'Invalid {name}: {value!r}')
    validator.__name__ = f'cast_{name}'
    validator.__qualname__ = validator.__name__
    return validator

def seq_validator(outer: Type, base: Type, iv: TypeValidator) -> TypeValidator:
    """
    generate generic sequence-type typecast validator for the specified type

    :param outer: outer sequence type definition
    :param iv:    validation for inner sequence type
    :return:      custom sequence validation function
    """
    name = _anno_name(outer)
    def validator(value: Sequence[Any]):
        if not isinstance(value, Sequence) or isinstance(value, str):
            raise ValidationError(f'Invalid {name}: {value!r}')
        values = []
        for n, item in enumerate(value, 0):
            try:
                newitem = iv(item)
                values.append(newitem)
            except Exception as e:
                raise ValidationError(f'Index {n}, {e}') from None
        return base(values)
    validator.__name__ = f'validate_{name}'
    validator.__qualname__ = validator.__name__
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
    def validator(value: Mapping[Any, Any]):
        if not isinstance(value, Mapping):
            raise ValidationError(f'Invalid {name}: {value!r}')
        values = {}
        for k,v in value.items():
            newkey = kv(k)
            newval = vv(v)
            values[newkey] = newval
        return base(values)
    validator.__name__ = f'validate_{name}'
    validator.__qualname__ = validator.__name__
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
    validator.__name__ = f'validate_{name}'
    validator.__qualname__ = validator.__name__
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
    name = _anno_name(anno)
    def validator(value: Any):
        if isinstance(value, args):
            return value
        for validator in validators:
            try:
                return validator(value)
            except Exception:
                pass
        raise ValidationError(f'Invalid Value: {value!r}')
    validator.__name__ = f'validate_{name}'
    validator.__qualname__ = validator.__name__
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
    generate a tcheck if type is an iterable list, set, tuple, etcype-validator for the given annotation

    :param anno: annotation to validate for
    :return:     field validator for the given annotation
    """
    # check for standard validator types
    if anno is None or anno is type(None):
        return none_validator
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
        return seq_validator(anno, base, validator)
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

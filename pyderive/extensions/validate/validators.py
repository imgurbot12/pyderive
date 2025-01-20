"""
Type/Field Validator Implementations
"""
import functools
import sys
import json
import typing
from enum import Enum
from typing import (
    Any, Callable, Dict, ForwardRef, Generic, Iterable, List, Literal,
    Mapping, Optional, Protocol, Sequence, Tuple, Type, TypeVar, Union, cast)
from typing_extensions import Annotated, runtime_checkable, get_origin, get_args

from ..serde import is_sequence
from ..utils import deref
from ...abc import MISSING, FieldDef, FieldValidator
from ...compat import is_stddataclass
from ...dataclasses import is_dataclass, asdict

#TODO: implement better string format for error objects

#** Variables **#
__all__ = [
    'TypeValidator',

    'is_autogen',
    'is_sequence',
    'type_validator',
    'field_validator',
    'register_validator',

    'ValidationError',
    'FieldValidationError',

    'Validator',
    'PreValidator',
    'PostValidator',
]

#: generic typevar
T = TypeVar('T')

#: type validator / type translation function
TypeValidator = Callable[[T], T]

#: validator marker to denote function was autogenerated
VALIDATOR_MARKER = '__autogen__'

#: global type-validator registry
TYPE_VALIDATORS: Dict[Type, List[TypeValidator]] = {}

#** Functions **#

def _anno_name(anno: Type) -> str:
    """generate clean annotation name"""
    if anno is str:
        return 'string'
    if anno is int:
        return 'integer'
    return getattr(anno, '__name__', None) or str(anno).split('.', 1)[-1]

def _wrap(name: str) -> Callable[[Callable], Callable]:
    def wrapper(func: Callable) -> Callable:
        func.__name__ = f'validate_{name}'
        func.__qualname__ = func.__name__
        return func
    return wrapper

@functools.lru_cache(maxsize=None)
def _runtime_checkable(p: Type) -> Type:
    try:
        return runtime_checkable(p)
    except TypeError:
        return p

def is_autogen(f: Callable) -> bool:
    """
    return true if function validator was auto-generated

    :param f: function to determine if auto-generated
    :return:  true if autogenerated, else false
    """
    return hasattr(f, VALIDATOR_MARKER)

def check_missing(anno: Union[Type, Iterable[Type]], value: Any):
    """
    check that the specified value is not MISSING
    """
    if value is MISSING:
        anno_tup = tuple(anno) if is_sequence(anno) else (anno, ) #type: ignore
        raise ValidationError(anno_tup, None, 'missing', 'Field required')

def none_validator(value: Any):
    """
    validate value is a none-type
    """
    if value is not None:
        raise ValidationError((None, ), value, 'not_null', 'Value is not Null')

def simple_validator(anno: Type[T], typecast: bool) -> TypeValidator[T]:
    """
    generate generic validation function for the specified type

    :param anno:     python type to cast value as
    :param typecast: allow typecasting if true
    :return:         type-validator that attempts typecast
    """
    name = _anno_name(anno)
    @_wrap(name)
    def validator(value: Any) -> Any:
        check_missing(anno, value)
        if isinstance(value, anno):
            return value
        if typecast:
            # attempt normal casting
            try:
                return anno(value) #type: ignore
            except (ValueError, ValidationError):
                pass
        raise ValidationError((anno, ), value,
            f'parse_{name}', f'Invalid {name}')
    return validator

def literal_validator(anno: Tuple[T]) -> TypeValidator[T]:
    """
    generate literal value validator for the specified value

    :param anno: python values acting as annotation
    :return:     type-validator that attempts typecast
    """
    name = f'validate_literal({anno!r})'
    @_wrap(name)
    def validator(value: Any) -> Any:
        check_missing(value, anno)
        if value in anno:
            return value
        raise ValidationError((Literal[anno], ), value,
            'invalid_literal', 'Unexpected Value')
    return validator

def seq_validator(outer: Type,
    base: Type, iv: TypeValidator, typecast: bool) -> TypeValidator:
    """
    generate generic sequence-type typecast validator for the specified type

    :param outer:    outer sequence type definition
    :param base:     base annotation for inner value
    :param iv:       validation for inner sequence type
    :param typecast: allow typecasting when enabled
    :return:         custom sequence validation function
    """
    name = _anno_name(outer)
    @_wrap(name)
    def validator(value: Sequence[Any]):
        check_missing(outer, value)
        if (base and not typecast and not isinstance(value, base)) \
            or not is_sequence(value):
            raise ValidationError((outer, ),
                value, 'parse_sequence', 'Invalid Sequence')
        values = []
        for n, item in enumerate(value, 0):
            try:
                newitem = iv(item)
                values.append(newitem)
            except ValidationError as e:
                e.path.insert(0, str(n))
                raise e
            except Exception as e:
                raise ValidationError((outer,), value, str(e), [str(n)]) from None
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
        check_missing(outer, value)
        if not isinstance(value, Mapping):
            raise ValidationError((outer, ), value,
                'parse_map', 'Invalid Mapping')
        values = {}
        for k,v in value.items():
            try:
                newkey = kv(k)
            except ValidationError as e:
                e.message = 'Invalid Key'
                raise e
            try:
                newval = vv(v)
            except ValidationError as e:
                e.path.insert(0, str(k))
                raise e
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
        check_missing(anno, value)
        # convert to tuple or raise error
        if not isinstance(value, tuple):
            if not typecast:
                raise ValidationError((anno, ),
                    value, 'parse_tuple', 'Invalid tuple')
            value = tuple(value)
        # ensure number of min-values matches
        if len(value) < len(validators):
            raise ValidationError((anno, ),
                value, 'parse_tuple', 'Not enough items')
        # ensure number of max-values on no elipsis
        if not ellipsis and len(value) > len(validators):
            raise ValidationError((anno, ),
                value, 'parse_tuple', 'Too many items')
        # iterate and validate items in tuple
        values = []
        for n, (item, validator) in enumerate(zip(value, validators), 0):
            try:
                newitem = validator(item)
            except ValidationError as e:
                e.path.insert(0, str(n))
                raise e
            values.append(newitem)
        # iterate remaining items if ellipsis is enabled
        if len(values) < len(value):
            validator = validators[-1]
            for n, item in enumerate(value[len(values):], len(values)):
                try:
                    newitem = validator(item)
                except ValidationError as e:
                    e.path.insert(0, str(n))
                    raise e
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
        check_missing(anno, value)
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
        raise ValidationError((anno, ), value, 'parse_enum', 'Invalid Enum')
    return validator

def subclass_validator(anno: Type) -> TypeValidator:
    """
    generate subclass-validator for the specified type

    :param anno: base annotation
    :return:     generated type validator
    """
    # ensure protocols are runtime-checkable
    is_protocol = Protocol in anno.__mro__
    if is_protocol:
        anno = _runtime_checkable(anno)
    # generate validator
    @_wrap(_anno_name(anno))
    def validator(value: Any):
        check_missing(anno, value)
        if is_protocol:
            if isinstance(value, type) and anno in value.__mro__:
                return value
        elif isinstance(value, type) and issubclass(value, anno):
            return value
        raise ValidationError((anno, ), value, 'parse_type', 'Invalid Subclass')
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
    anno_names  = []
    annotations = []
    while wrapped:
        sanno = wrapped.pop()
        origin, subargs = get_origin(sanno), get_args(sanno)
        if origin is None:
            annotations.append(sanno)
            continue
        elif origin is Annotated \
            and not any(isinstance(a, Validator) for a in subargs):
            wrapped.append(subargs[0])
        elif origin is Union:
            wrapped.extend(subargs)
        # track annotation names for validation-error
        anno_name = origin or sanno
        if anno_name not in anno_names:
            anno_names.append(anno_name)
    anno_names  = tuple(anno_names)
    annotations = tuple(annotations)
    # generate valdiator object
    @_wrap(_anno_name(anno))
    def validator(value: Any):
        check_missing(annotations, value)
        if isinstance(value, annotations):
            return value
        for validator in validators:
            try:
                return validator(value)
            except ValueError:
                pass
        raise ValidationError(anno_names,
            value, 'parse_union', 'Unable to Match Union')
    return validator

def dclass_validator(anno: Type, typecast: bool) -> TypeValidator:
    """
    generate a dataclass type validator

    :param anno:     dataclass annotation
    :param typecast: attempt typecast into dataclass if enabled
    """
    name = _anno_name(anno)
    @_wrap(name)
    def validator(value: Any):
        check_missing(anno, value)
        force_typecast = False
        original_value = value
        if isinstance(value, anno):
            return value
        if is_generic_instance(value, anno):
            value          = asdict(value)
            force_typecast = True
        if typecast or force_typecast:
            if isinstance(value, Mapping):
                try:
                    return anno(**value)
                except (TypeError, ValueError):
                    pass
            if isinstance(value, (set, Sequence)):
                try:
                    return anno(*value)
                except (TypeError, ValueError):
                    pass
            try:
                return anno(value)
            except (TypeError, ValueError):
                pass
        raise ValidationError((anno, ), original_value,
            f'parse_object', 'Unable to Convert to Dataclass')
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

def ref_validator(cls: Type, ref: ForwardRef, typecast: bool) -> TypeValidator:
    """
    generate forward-reference validator to process forward-reference

    :param cls:      dataclass associated w/ reference
    :param ref:      forward-reference to later resolve
    :param typecast: allow for typecasting when enabled
    :return:         forward-reference validator function
    """
    # generate dereference function w/ cache to avoid repeat lookups
    @functools.lru_cache(maxsize=None)
    def deref_validator() -> TypeValidator:
        anno = deref(cls, ref)
        return type_validator(anno, typecast)
    # generate validator
    @_wrap(ref.__forward_arg__)
    def validator(value: Any) -> Any:
        return deref_validator()(value)
    return validator

def identity(value: Any) -> Any:
    return value

def type_validator(anno: Type,
    typecast: bool, cls: Optional[Type] = None) -> TypeValidator:
    """
    generate a type-validator for the given annotation

    :param anno:     annotation to validate for
    :param typecast: allow for typecasting when enabled
    :param cls:      dataclass associated w/ annotation assignment
    :return:         field validator for the given annotation
    """
    # check if string/forward-reference
    if isinstance(anno, (str, ForwardRef)):
        if cls is None:
            raise TypeError(f'Cannot Resolve ForwardReferences: {anno!r}')
        str_anno = ForwardRef(anno) if isinstance(anno, str) else anno
        return ref_validator(cls, str_anno, typecast)
    # convert typevar based on bound condition
    if isinstance(anno, TypeVar):
        anno = getattr(anno, '__bound__') or Any
    # check for standard validator types
    if anno is None or anno is type(None):
        return none_validator
    # check if type is specifically registered
    if anno in TYPE_VALIDATORS:
        return chain_validators(TYPE_VALIDATORS[anno])
    # check for `Enum` annotation
    if isinstance(anno, type) and issubclass(anno, Enum):
        return enum_validator(anno, typecast)
    # check if dataclass instance
    if is_dataclass(anno) or is_stddataclass(anno):
        return dclass_validator(anno, typecast)
    # check for `Any` annotation
    if anno is Any:
        return identity
    # ensure protocols are runtime-checkable
    if isinstance(anno, type) and Protocol in anno.__mro__:
        anno = _runtime_checkable(anno)
    # check for `Annotated` validator definitions
    origin, args = get_origin(anno), get_args(anno)
    if origin is Annotated:
        middle    = [type_validator(args[0], typecast, cls)]
        pre, post = [], []
        for value in args[1:]:
            if isinstance(value, PreValidator):
                pre.append(value.validator)
            elif isinstance(value, PostValidator):
                post.append(value.validator)
            elif isinstance(value, Validator):
                middle.append(value.validator)
        return chain_validators([*pre, *middle, *post])
    # support `Literal` annotation
    if origin is Literal:
        return literal_validator(args)
    # check for `Type` annotation
    if origin is type:
        return subclass_validator(args[0])
    # check for `Union` annotation
    if origin is Union:
        validators = [type_validator(arg, typecast, cls) for arg in args]
        return union_validator(anno, args, validators)
    # check for `tuple` annotation
    if origin is tuple:
        ellipsis   = Ellipsis in args
        validators = [type_validator(arg, typecast)
            for arg in args if arg is not Ellipsis]
        return tup_validator(anno, validators, ellipsis, typecast)
    # check for `Sequence` annotation
    if origin in (list, set, Sequence):
        base      = cast(Type, list if origin is Sequence else origin)
        validator = type_validator(args[0], typecast, cls)
        return seq_validator(anno, base, validator, typecast)
    # check for `Mapping` annnotation
    if origin in (dict, Mapping):
        base          = cast(Type, dict if origin is Mapping else origin)
        key_validator = type_validator(args[0], typecast, cls)
        val_validator = type_validator(args[1], typecast, cls)
        return map_validator(anno, base, key_validator, val_validator)
    # support generic-aliases
    if origin is not None:
        anno = origin
    # raise error on unsupported generic
    if isinstance(anno, Generic):
        raise TypeError(f'Cannot validate type: {anno!r}')
    # support `NewType`
    super_type = getattr(anno, '__supertype__', None)
    if super_type is not None:
        anno = super_type
    # attempt a simple/typecast annotation on anything else
    return simple_validator(anno, typecast)

def convert_error(inst: Any, field: FieldDef, value: Any, err: 'ValidationError'):
    """convert validation-error into field-validation-error"""
    obj     = inst if isinstance(inst, type) else type(inst)
    name    = obj.__name__
    anno    = '/'.join(_anno_name(a) for a in err.anno)
    vtype   = _anno_name(type(value))
    message = err.message
    if err.etype != 'missing':
        message = f'Input should be a valid {anno}' + \
            f', unable to parse {vtype}. {err.message}'
    new_err = FieldValidationError(name, field, err.value, err.etype, message)
    if err.path is not None:
        new_err.path.extend(err.path)
    return new_err

def field_validator(cls: Type,
    field: FieldDef, typecast: bool = False) -> FieldValidator:
    """
    generate field-validator for the specified field definition

    :param cls:      dataclass object associated w/ field
    :param field:    field to add validator for
    :param typecast: allow for typecasting when enabled
    :return:         validation function for field
    """
    validator = type_validator(field.anno, typecast, cls=cls)
    def field_validator(self, field: FieldDef, value: Any):
        try:
            return validator(value)
        except FieldValidationError as e:
            e.path.insert(0, field.name)
            raise e
        except ValidationError as e:
            raise convert_error(self, field, value, e) from None
        except ValueError as e:
            err  = str(e)
            obj  = self if isinstance(self, type) else type(self)
            name = obj.__name__
            etype = f'parse_{_anno_name(field.anno)}'
            raise FieldValidationError(name, field, value, etype, err) from None
    field_validator.__name__ = f'validate_{field.name}'
    field_validator.__qualname__ = field_validator.__name__
    setattr(field_validator, '__autogen__', True)
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
    """Exception Raised during Validation Error"""
    anno:    Tuple[Type, ...]
    value:   Any
    etype:   str
    message: str
    path:    List[str]

    def __init__(self, anno, value, etype, message, path = None):
        self.etype   = etype
        self.anno    = anno
        self.value   = value
        self.message = message
        self.path    = path or []

    def __str__(self) -> str:
        return '\n' + '\n'.join([
            f'  ErrType:  {self.etype!r}',
            f'  Path:     {self.path!r}',
            f'  Input:    {self.value!r} ({_anno_name(type(self.value))})',
            f'  Expected: {self.anno!r}',
            f'  Message:  {self.message!r}',
        ])

class FieldValidationError(ValidationError):
    """Exception Raised When Field Validation Fails"""
    etype:   str
    title:   str
    field:   FieldDef
    value:   Any
    message: str

    def __init__(self, title, field, value, etype, message):
        self.etype       = etype
        self.title       = title
        self.field       = field
        self.path        = [self.field.name]
        self.value       = value
        self.message     = message
        self.error_count = 1

    def __str__(self) -> str:
        return '\n' + '\n'.join([
            f'  ErrType:  {self.etype} (count: {self.error_count})',
            f'  Field:    {self.title}.{self.field.name}',
            f'  Path:     {self.path!r}',
            f'  Input:    {self.value!r} ({_anno_name(type(self.value))})',
            f'  Expected: {_anno_name(self.field.anno)}',
            f'  Message:  {self.message!r}',
        ])

    def errors(self) -> List[dict]:
        """generate errors dictionary object"""
        return [{
            'type':  self.etype,
            'path':  tuple(self.path),
            'msg':   self.message,
            'input': self.value,
        }]

    def json(self) -> str:
        """generate json for errors"""
        return json.dumps(self.errors())

class Validator:
    """Annotated Validator Indicator"""
    __slots__ = ('validator', )

    def __init__(self, validator: TypeValidator):
        if not callable(validator):
            raise TypeError('Validator: {validator!r} is not callable')
        self.validator = validator

    def __call__(self, *args, **kwargs):
        return self.validator(*args, **kwargs)

    def __class_getitem__(cls, validator: TypeValidator) -> 'Validator':
        return cls(validator)

class PreValidator(Validator):
    """Pre Typecast Validator Indicator"""
    pass

class PostValidator(Validator):
    """Post Typecast Validator Indicator"""
    pass

#** Imports **#
from .generic import is_generic_instance

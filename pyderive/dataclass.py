"""
DataClass stdlib recreation using existing helpers
"""
import abc
import copy
from typing import * 
from typing_extensions import dataclass_transform

from .abc import *
from .parse import *
from .compile import *

#** Variables **#
__all__ = [
    'InitVar', 
    'MISSING', 
    
    'is_dataclass',
    'field', 
    'fields',
    'asdict',
    'dataclass'
]

#: dataclass fields attribute
FIELD_ATTR = '__derive_datafields__'

#: type alias for dataclass converter function
T = TypeVar('T')

#: type for type-alias
TypeT = Type[T]

#: typehint for dataclass creator function
DataFunc = Callable[[TypeT], TypeT] 

_hash_add  = lambda _, fields: create_hash(fields)
_hash_none = lambda *_: None
def _hash_err(cls, _):
    raise TypeError(
        f'Cannot override attribute __hash__ in class {cls.__name__}')

#: table of hash controls -> hash-action
#  (unsafe_hash, eq, frozen, has_explicit_hash) -> Callable
HASH_ACTIONS: Dict[Tuple[bool, bool, bool, bool], Any] = {
    (False, False, False, False): None,
    (False, False, False, True ): None,
    (False, False, True,  False): None,
    (False, False, True,  True ): None,
    (False, True,  False, False): _hash_none,
    (False, True,  False, True ): None,
    (False, True,  True,  False): _hash_add,
    (False, True,  True,  True ): None,
    (True,  False, False, False): _hash_add,
    (True,  False, False, True ): _hash_err,
    (True,  False, True,  False): _hash_add,
    (True,  False, True,  True ): _hash_err,
    (True,  True,  False, False): _hash_add,
    (True,  True,  False, True ): _hash_err,
    (True,  True,  True,  False): _hash_add,
    (True,  True,  True,  True ): _hash_err,
}

#** Functions **#

def field(*_, **kwargs) -> Field:
    """
    specify field configurations for a dataclass attribute
    """
    return Field(MISSING, MISSING, **kwargs) #type: ignore

def is_dataclass(cls) -> bool:
    """
    return true if object is a dataclass

    :param cls: object-type/instance to check
    :return:    true if object is a dataclass
    """
    return hasattr(cls, FIELD_ATTR)

def fields(cls) -> List[Field]:
    """
    retrieve fields associated w/ the given dataclass

    :param cls: dataclass object class instance
    :return:    field dictionary
    """
    if not is_dataclass(cls):
        raise TypeError('fields() should with a dataclass type or instance')
    return getattr(cls, FIELD_ATTR)

def _asdict_inner(obj, rec: int, factory: Type[dict], lvl: int):
    """inner dictionary-ify function to convert dataclass fields into dict"""
    # stop recursin after limit
    if rec > 0 and lvl >= rec:
        return obj
    # dataclass
    lvl += 1
    if is_dataclass(obj):
        result = []
        for f in fields(obj):
            attr  = getattr(obj, f.name)
            value = _asdict_inner(attr, rec, factory, lvl)
            result.append((f.name, value))
        return factory(result)
    # named-tuple
    elif isinstance(obj, tuple) and hasattr(obj, '_fields'):
        return type(obj)(*[_asdict_inner(v, rec, factory, lvl) for v in obj])
    # standard list/tuple
    elif isinstance(obj, (list, tuple)):
        return type(obj)(_asdict_inner(v, rec, factory, lvl) for v in obj)
    elif isinstance(obj, dict):
        return type(obj)((_asdict_inner(k, rec, factory, lvl),
                          _asdict_inner(v, rec, factory, lvl))
                         for k, v in obj.items())
    else:
        return copy.deepcopy(obj) 

def asdict(cls, *, recurse: int = 0, dict_factory: Type[dict]=dict) -> dict:
    """
    convert dataclass object into dictionary of field-values

    :param cls: dataclass object class instance
    :return:    field instances as dict
    """
    if not is_dataclass(cls):
        raise TypeError('asdict() should be called on dataclass instances')
    return _asdict_inner(cls, recurse, dict_factory, 0) #type: ignore

@dataclass_transform(field_specifiers=(FieldDef, Field, field))
def _process_class(
    cls: TypeT,
    init:        bool = True,
    repr:        bool = True,
    eq:          bool = True,
    order:       bool = False,
    unsafe_hash: bool = False,
    frozen:      bool = False,
    match_args:  bool = True,
    kw_only:     bool = False,
    slots:       bool = False,
    recurse:     bool = False,
) -> TypeT:
    # valdiate settings
    if order and not eq:
        raise ValueError('eq must be true if order is true')
    # parse and conregate fields
    struct = parse_fields(cls, recurse=recurse)
    fields = flatten_fields(struct)
    freeze = frozen or any(f.frozen for f in fields)
    # assign fields to dataclass
    setattr(cls, FIELD_ATTR, fields)
    # build functions
    if init:
        post_init = hasattr(cls, POST_INIT)
        assign_func(cls, create_init(fields, kw_only, post_init, frozen))
    if repr:
        assign_func(cls, create_repr(fields))
    if eq:
        assign_func(cls, create_compare(fields, '__eq__', '=='))
    if order:
        funcs = [('lt', '<'), ('le', '<='), ('gt', '>'), ('ge', '>=')]
        for name, op in funcs:
            fname = f'__{name}__'
            func  = create_compare(fields, fname, op)
            if assign_func(cls, func):
                raise TypeError(f'Cannot override attibute {fname} '
                                f'in class {cls.__name__}. Consider '
                                'using functools.total_ordering')
    if freeze:
        freeze_fields(cls, struct, frozen)
    # build hash function based on current state
    class_dict  = cls.__dict__
    class_eq    = class_dict.get('__eq__', None)
    class_hash  = class_dict.get('__hash__', MISSING)
    explicit    = not (class_hash in (MISSING, None) and class_eq)
    hash_args   = (bool(unsafe_hash), bool(eq), bool(frozen), explicit)
    hash_action = HASH_ACTIONS[hash_args]
    if hash_action is not None:
        result = hash_action(cls, fields)
        assign_func(cls, result, '__hash__')
    # handle match-args
    if match_args:
        match = tuple(f.name for f in fields if f.init)
        assign_func(cls, match, '__match_args__') #type: ignore
    # add slots
    if slots:
        cls = add_slots(cls, fields, freeze)
    # update abstraction-methods on re-creation and return
    abc.update_abstractmethods(cls)
    return cls

@overload
@dataclass_transform(field_specifiers=(FieldDef, Field, field))
def dataclass(cls: Type[T]) -> Type[T]:
    ...

@overload
def dataclass(*,
    init:        bool = True,
    repr:        bool = True,
    eq:          bool = True,
    order:       bool = False,
    unsafe_hash: bool = False,
    frozen:      bool = False,
    match_args:  bool = True,
    kw_only:     bool = False,
    slots:       bool = False,
    recurse:     bool = False,
) -> DataFunc:
    ...

def dataclass(cls: Optional[TypeT] = None, *_, **kw) -> Union[TypeT, DataFunc]:
    """
    generate a dataclass with the specified settings

    :param cls:         dataclass template class definition
    :param init:        enable automatic init generation
    :param repr:        enable automatic repr generation
    :param eq:          enable automatic equals generation
    :param order:       enable automatic order generation
    :param unsafe_hash: enable unsafe-hash function if unsafe
    :param frozen:      ensure object fields cannot be modified
    :param match_args:  enable match-args generation
    :param kw_only:     fields are keyword-only
    :param slots:       enable slots generation
    :param recurse:     recursively search and compile fields from base-classes
    :return:            dataclass type object
    """
    @dataclass_transform(field_specifiers=(FieldDef, Field, field))
    def wrapper(cls: TypeT) -> TypeT:
        return _process_class(cls, **kw)
    return wrapper if cls is None else wrapper(cls)

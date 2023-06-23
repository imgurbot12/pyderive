"""
DataClass stdlib recreation using existing helpers
"""
import abc
import copy
from typing import * 
from typing_extensions import dataclass_transform, runtime_checkable

from .abc import *
from .parse import *
from .compile import *
from .compat import is_stddataclass, convert_params

#** Variables **#
__all__ = [
    'InitVar', 
    'MISSING', 
    'DataClassLike',
    'FrozenInstanceError',
 
    'is_dataclass',
    'field', 
    'fields',
    'asdict',
    'dataclass'
]

#: dataclass fields attribute
FIELD_ATTR = '__datafields__'

#: dataclas params attribute
PARAMS_ATTR = '__dataparams__'

#: field generic type
F = TypeVar('F', bound=FieldDef)

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

def field(*_, **kwargs) -> Any:
    """
    specify field configurations for a dataclass attribute
    """
    return Field('', MISSING, **kwargs)

def is_dataclass(cls) -> bool:
    """
    return true if object is a dataclass

    :param cls: object-type/instance to check
    :return:    true if object is a dataclass
    """
    return hasattr(cls, FIELD_ATTR)

@overload
def fields(cls: Any, all_types: bool = False) -> List[FieldDef]:
    ...

@overload
def fields(cls: 'DataClassLike[F]', all_types: bool = False) -> List[F]:
    ...

def fields(cls, all_types: bool = False):
    """
    retrieve fields associated w/ the given dataclass

    :param cls:       dataclass object class instance
    :param all_types: return all field-types or just standard fields
    :return:          field dictionary
    """
    if not is_dataclass(cls):
        raise TypeError('fields() should with a dataclass type or instance')
    fields = getattr(cls, FIELD_ATTR)
    if not all_types:
        fields = [f for f in fields if f.field_type == FieldType.STANDARD]
    return fields

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

def asdict(cls, *, recurse: int = 0, dict_factory: Type[dict] = dict) -> dict:
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
    init:        Optional[bool] = None,
    repr:        Optional[bool] = None,
    eq:          bool = True,
    order:       bool = False,
    unsafe_hash: bool = False,
    frozen:      bool = False,
    match_args:  bool = True,
    kw_only:     bool = False,
    slots:       bool = False,
    recurse:     bool = False,
    field:       Type[FieldDef] = Field,
) -> TypeT:
    # valdiate settings
    if order and not eq:
        raise ValueError('eq must be true if order is true')
    # convert params for stdlib dataclasses
    isdataclass = is_dataclass(cls)
    if not isdataclass and is_stddataclass(cls):
        convert_params(cls)
    # parse and conregate fields
    struct = parse_fields(cls, factory=field, recurse=recurse)
    fields = flatten_fields(struct)
    freeze = frozen or any(f.frozen for f in fields)
    # validate settings and save fields/params
    params = DataParams(init, repr, eq, order, unsafe_hash, 
        frozen, match_args, kw_only, slots, recurse, field)
    if isdataclass:
        ofields = getattr(cls, FIELD_ATTR)
        oparams = getattr(cls, PARAMS_ATTR)
        # ensure there are no frozen conflicts
        if frozen and not (oparams.frozen or all(f.frozen for f in ofields)):
            raise TypeError(
                'cannot inherit frozen dataclass from a non-frozen one')
        if not frozen and (oparams.frozen or any(f.frozen for f in ofields)):
            raise TypeError(
                'cannot inherit non-frozen dataclass from a frozen one')
    # ensure slots dont conflict with partially frozen dataclasses
    if slots and not frozen and any(f.frozen for f in fields):
        raise TypeError(
            'cannot assign slots for partially frozen dataclass')
    # assign fields to dataclass
    setattr(cls, FIELD_ATTR, fields)
    setattr(cls, PARAMS_ATTR, params)
    # build functions
    if init or init is None:
        overwrite = init is True
        post_init = hasattr(cls, POST_INIT)
        initfunc  = create_init(fields, kw_only, post_init, frozen)
        assign_func(cls, initfunc, overwrite=overwrite)
    if repr or repr is None:
        overwrite = repr is True
        assign_func(cls, create_repr(fields), overwrite=overwrite)
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
        freeze_fields(cls, fields, frozen)
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
    if hasattr(abc, 'update_abstractmethods'):
        abc.update_abstractmethods(cls)
    return cls

@overload
@dataclass_transform(field_specifiers=(FieldDef, Field, field))
def dataclass(cls: Type[T], 
    init:        Optional[bool] = None,
    repr:        Optional[bool] = None,
    eq:          bool = True,
    order:       bool = False,
    unsafe_hash: bool = False,
    frozen:      bool = False,
    match_args:  bool = True,
    kw_only:     bool = False,
    slots:       bool = False,
    recurse:     bool = False,
    field:       Type[FieldDef] = Field,
) -> Type[T]:
    ...

@overload
def dataclass(*,
    init:        Optional[bool] = None,
    repr:        Optional[bool] = None,
    eq:          bool = True,
    order:       bool = False,
    unsafe_hash: bool = False,
    frozen:      bool = False,
    match_args:  bool = True,
    kw_only:     bool = False,
    slots:       bool = False,
    recurse:     bool = False,
    field:       Type[FieldDef] = Field,
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
    :param field:       field-factory baseclass
    :return:            dataclass type object
    """
    @dataclass_transform(field_specifiers=(FieldDef, Field, field))
    def wrapper(cls: TypeT) -> TypeT:
        return _process_class(cls, **kw)
    return wrapper if cls is None else wrapper(cls)

#** Classes **#

@runtime_checkable
class DataClassLike(Generic[F], Protocol):
    """Protocol for DataClass-Like Objects"""
    __datafields__: List[F]

class DataParams:
    """Pseudo Dataclass to store parameters used to generate dataclass"""
    __slots__ = (
        'init', 
        'repr',
        'eq', 
        'order', 
        'unsafe_hash', 
        'frozen', 
        'match_args', 
        'kw_only', 
        'slots', 
        'recurse', 
        'field')

    def __init__(self,
        init:        Optional[bool],
        repr:        Optional[bool],
        eq:          bool,
        order:       bool,
        unsafe_hash: bool,
        frozen:      bool,
        match_args:  bool,
        kw_only:     bool,
        slots:       bool,
        recurse:     bool,
        field:       Type[FieldDef],
    ):
        self.init        = init
        self.repr        = repr
        self.eq          = eq
        self.order       = order
        self.unsafe_hash = unsafe_hash
        self.frozen      = frozen
        self.match_args  = match_args
        self.kw_only     = kw_only
        self.slots       = slots
        self.recurse     = recurse
        self.field       = field

"""
Custom DataClass Internal Types
"""
from abc import abstractmethod
from enum import IntEnum
from typing import (
    Any, Callable, Dict, Generic, List, Literal, Optional,
    Protocol, Type, TypeVar, Union)
from typing_extensions import Annotated, Self, \
    runtime_checkable, get_origin, get_args

#** Variables **#
__all__ = [
    'has_default',
    'get_initvar',

    'T',
    'F',
    'TypeT',
    'DataFunc',

    'has_default',

    'MISSING',
    'InitVar',
    'FrozenInstanceError',
    'Fields',
    'DefaultFactory',
    'FieldType',
    'FieldDef',
    'Field',
    'FlatStruct',
    'ClassStruct',
    'DataClassLike',
]

#: generic typevar
T = TypeVar('T')

#: generic typevar for field
F = TypeVar('F', bound='FieldDef')

#: generic typevar bound to type
TypeT = TypeVar('TypeT', bound=Type)

#: InitVar Implementation
InitVar = Annotated[T, 'INIT-VAR']

#: typehint for dataclass creator function
DataFunc = Callable[[TypeT], TypeT]

#: type definition for a list of fields
Fields = List['FieldDef']

#: optional dictionary typehint
OptDict = Optional[Dict[str, Any]]

#: callable factory type hint
DefaultFactory = Union['MISSING', None, Callable[[], Any]]

#: field validator function
FieldValidator = Callable[[Any, F, Any], Any]

#: optional field validator function
OptValidator = Optional[FieldValidator]

#: optional settings for when to hide values in repr
ReprHide = Union[Literal['null'], Literal['empty']]

#** Functions **#

def has_default(field: 'FieldDef') -> bool:
    """return true if field has default"""
    return field.default is not MISSING or field.default_factory is not MISSING

def get_initvar(anno: Type) -> Optional[Type]:
    """return inner annotation if annotation is init-var"""
    origin, args = get_origin(anno), get_args(anno)
    if origin is Annotated and len(args) == 2 and args[1] == 'INIT-VAR':
        return args[0]

#** Classes **#

class MISSING:
    pass

class FrozenInstanceError(AttributeError):
    pass

class FieldType(IntEnum):
    STANDARD = 1
    INIT_VAR = 2

@runtime_checkable
class FieldDef(Protocol[TypeT]):
    name:            str
    anno:            TypeT
    default:         Any            = MISSING
    default_factory: DefaultFactory = MISSING
    init:            bool           = True
    repr:            bool           = True
    hash:            Optional[bool] = None
    compare:         bool           = True
    iter:            bool           = True
    kw_only:         bool           = False
    frozen:          bool           = False
    validator:       OptValidator   = None
    metadata:        Dict[str, Any] = {}
    field_type:      FieldType      = FieldType.STANDARD

    @abstractmethod
    def __init__(self, name: str, anno: Type, default: Any = MISSING):
        raise NotImplementedError

    def __compile__(self, cls: Type):
        """run finalize when field variables are finished compiling"""
        pass

class Field(FieldDef[TypeT]):

    def __init__(self,
        name:            str,
        anno:            TypeT,
        default:         Any            = MISSING,
        default_factory: DefaultFactory = MISSING,
        init:            bool           = True,
        repr:            bool           = True,
        hash:            Optional[bool] = None,
        compare:         bool           = True,
        iter:            bool           = True,
        kw_only:         bool           = False,
        frozen:          bool           = False,
        validator:       OptValidator   = None,
        metadata:        OptDict        = None,
        field_type:      FieldType      = FieldType.STANDARD
    ):
        self.name            = name
        self.anno            = anno
        self.default         = default
        self.default_factory = default_factory
        self.init            = init
        self.repr            = repr
        self.hash            = hash
        self.compare         = compare
        self.kw_only         = kw_only
        self.iter            = iter
        self.frozen          = frozen
        self.validator       = validator
        self.metadata        = metadata or {}
        self.field_type      = field_type

class FlatStruct:

    def __init__(self,
        order:  Optional[List[str]]           = None,
        fields: Optional[Dict[str, FieldDef]] = None,
    ):
        self.order  = order  or []
        self.fields = fields or dict()

    def ordered_fields(self) -> Fields:
        """return fields in order they were assigned"""
        return [self.fields[name] for name in self.order]

class ClassStruct(FlatStruct):
    base:        Optional[Type]
    annotations: Optional[Dict[str, Any]]

    def __init__(self, *args, parent: Optional[Self] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent      = parent
        self.base        = None
        self.annotations = None

    def is_base_compiled(self, base: Type) -> bool:
        """
        check if baseclass is already compiled

        :param base: baseclass to confirm already compiled
        :return:     true if baseclass found in class-struct tree
        """
        if self.base is not None and self.base == base:
            return True
        if self.parent is not None:
            return self.parent.is_base_compiled(base)
        return False

    def is_anno_compiled(self, anno: Dict[str, Any]) -> bool:
        """
        check if annotations are already compiled

        :param anno: annotation to confirm already compiled
        :return:     true if annotations are already compiled
        """
        if self.annotations is not None and self.annotations == anno:
            return True
        if self.parent is not None:
            return self.parent.is_anno_compiled(anno)
        return False

@runtime_checkable
class DataClassLike(Generic[F], Protocol):
    """Protocol for DataClass-Like Objects"""
    __datafields__: List[F]

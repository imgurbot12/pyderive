"""
Custom DataClass Internal Types
"""
from abc import abstractmethod
from enum import IntEnum
from typing import *
from typing_extensions import Self, runtime_checkable

#** Variables **#
__all__ = [
    'T',
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
]

#: generic typevar
T = TypeVar('T')

#: type definition for a list of fields
Fields = List['FieldDef']

#: callable factory type hint
DefaultFactory = Union['MISSING', None, Callable[[], Any]]

#** Classes **#

class MISSING:
    pass

class InitVar(Generic[T]):
    __slots__ = ('type', )
    def __init__(self, type):
        self.type = type
    def __class_getitem__(cls, type):
        return cls(type)

class FrozenInstanceError(AttributeError):
    pass

class FieldType(IntEnum):
    STANDARD = 1
    INIT_VAR = 2

@runtime_checkable
class FieldDef(Protocol):
    name:            str
    anno:            Type
    default:         Any            = MISSING
    default_factory: DefaultFactory = MISSING
    init:            bool           = True
    repr:            bool           = True
    hash:            Optional[bool] = None
    compare:         bool           = True
    kw_only:         bool           = False
    frozen:          bool           = False
    field_type:      FieldType      = FieldType.STANDARD
 
    @abstractmethod
    def __init__(self, name: str, anno: Type, default: Any = MISSING):
        raise NotImplementedError

    def finalize(self):
        """run finalize when field variables are finished compiling"""
        pass

class Field(FieldDef):

    def __init__(self,
        name:            str,
        anno:            Type,
        default:         Any            = MISSING,
        default_factory: DefaultFactory = MISSING,
        init:            bool           = True,
        repr:            bool           = True,
        hash:            Optional[bool] = None,
        compare:         bool           = True,
        kw_only:         bool           = False,
        frozen:          bool           = False,
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
        self.frozen          = frozen
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
 
    def __init__(self, *args, parent: Optional[Self] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent

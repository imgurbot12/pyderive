"""
Custom DataClass Internal Types
"""
from abc import abstractmethod
from enum import IntEnum
from typing import *
from typing_extensions import Self, runtime_checkable

#: import MISSING type from dataclasses for compatability if available
try:
    from dataclasses import MISSING, InitVar, FrozenInstanceError #type: ignore
except ModuleNotFoundError:
    class MISSING: #type: ignore
        pass
    class _InitVarMeta(type):
        def __getitem__(self, _):
            return self
    class InitVar(metaclass=_InitVarMeta): #type: ignore
        pass
    class FrozenInstanceError(AttributeError): #type: ignore
        pass

#** Variables **#
__all__ = [
    'Fields',
    'DefaultFactory',
    'FieldType',
    'FieldDef',
    'Field',
    'FlatStruct',
    'ClassStruct',
    # exports
    'ClassVar',
    'InitVar', 
    'MISSING',
    'FrozenInstanceError'
]

#: type definition for a list of fields
Fields = List['FieldDef']

#: callable factory type hint
DefaultFactory = Union[MISSING, Callable[[], Any]]

#** Classes **#

class FieldType(IntEnum):
    STANDARD = 1
    INIT_VAR = 2

@runtime_checkable
class FieldDef(Protocol):
    name:            str
    anno:            Type
    default:         Any
    default_factory: DefaultFactory
    init:            bool
    repr:            bool
    hash:            bool
    compare:         bool
    kw_only:         bool
    frozen:          bool
    field_type:      FieldType
    
    @abstractmethod
    def __init__(self, name: str, anno: Type, default: Any = MISSING):
        raise NotImplementedError

class Field(FieldDef):

    def __init__(self,
        name:            str,
        anno:            Type,
        default:         Any            = MISSING,
        default_factory: DefaultFactory = MISSING,
        init:            bool           = True,
        repr:            bool           = True,
        hash:            bool           = True,
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

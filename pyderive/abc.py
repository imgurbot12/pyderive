"""
Custom DataClass Internal Types
"""
from typing import Type, Any, List, Set, Dict, Optional, ClassVar
from dataclasses import InitVar, MISSING, dataclass, field
from typing_extensions import Self

#** Variables **#
__all__ = [
    'FieldDef',
    'FlatStruct',
    'ClassStruct',
    # exports
    'ClassVar',
    'InitVar', 
    'MISSING',
]

#** Classes **#

@dataclass
class FieldDef:
    name:  str
    anno:  Type
    value: Any = MISSING

@dataclass
class FlatStruct:
    order:  List[str]           = field(default_factory=list)
    init:   Set[str]            = field(default_factory=set)
    args:   Set[str]            = field(default_factory=set)
    fields: Dict[str, FieldDef] = field(default_factory=dict)

@dataclass
class ClassStruct(FlatStruct):
    parent: Optional[Self] = None

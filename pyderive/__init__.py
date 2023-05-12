"""
Custom DataClass Compilation Helpers
"""

#** Variables **#
__all__ = [
    'Fields',
    'DefaultFactory',
    'FieldType',
    'FieldDef',
    'Field',
    'FlatStruct',
    'ClassStruct',
    'ClassVar',
    'InitVar', 
    'MISSING',
    'FrozenInstanceError',

    'remove_field',
    'parse_fields',
    'flatten_fields',

    'create_init',
    'create_repr',
    'create_compare',
    'create_hash',
    'assign_func',
    'add_slots',
    'freeze_fields',

    'is_dataclass',
    'field',
    'fields',
    'asdict',
    'dataclass',
]

#** Imports **#
from .abc import *
from .parse import *
from .compile import *
from .dataclass import *

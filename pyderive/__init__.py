"""
Custom DataClass Compilation Helpers
"""
from typing import Type, Any

from .abc import *
from .parse import *
from .compile import *
from .dataclasses import *
from . import compat

#** Variables **#
__all__ = [
    'compat',

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
    'DataClassLike',

    'BaseField',
]

#** Classes **#

@dataclass(recurse=True)
class BaseField(FieldDef):
    """dataclass field instance w/ better defaults"""
    name:            str            = ''
    anno:            Type           = type
    default:         Any            = field(default_factory=lambda: MISSING)
    default_factory: DefaultFactory = field(default_factory=lambda: MISSING) 

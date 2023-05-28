"""
Stdlib Dataclass Compatability Utils
"""
import sys
import importlib
from types import ModuleType
from typing import Optional, Type

from .abc import MISSING, FieldDef, FieldType, Fields

#** Variables **#
__all__ = ['monkey_patch', 'convert_fields', 'convert_params']

#: name of stdlib dataclass module
module_name = 'dataclasses'

#: preserved stdlib dataclass module for reference
stdlib_dataclasses: Optional[ModuleType] = None

#** Functions **#

def monkey_patch():
    """monkey-patch replace dataclasses w/ pyderive version"""
    global stdlib_dataclasses
    # skip repeated monkey-patching if already converted
    stdlib = sys.modules.get(module_name)
    if stdlib and stdlib is stdlib_dataclasses:
        return
    # generate custom module to export dataclass replacements
    from . import dataclasses as derive
    try:
        stdlib_dataclasses = importlib.import_module(module_name)
    except ImportError:
        pass
    sys.modules[module_name] = derive

def is_stddataclass(cls) -> bool:
    """
    check to see if class is a stdlib dataclass
    """
    dataclasses = stdlib_dataclasses or sys.modules.get(module_name)
    if not dataclasses:
        return False
    return dataclasses.is_dataclass(cls)

def convert_fields(cls, field: Type[FieldDef]) -> Fields:
    """
    convert stdlib dataclasses to pyderive dataclass

    :param cls:   dataclass object-type to convert fields for
    :param field: field definition to use when converting fields
    :return:      converted field attributes
    """
    # ensure type is dataclass or return
    dataclasses = stdlib_dataclasses or sys.modules.get(module_name)
    if not dataclasses:
        return []
    if not dataclasses.is_dataclass(cls):
        return []
    # create ftype conversion
    ftypes = {
        dataclasses._FIELD:         FieldType.STANDARD,
        dataclasses._FIELD_INITVAR: FieldType.INIT_VAR,
    }
    # convert field-types
    converted = []
    for f in getattr(cls, dataclasses._FIELDS).values():
        new = field(f.name, f.type, f.default)
        for name in (k for k in f.__slots__ if not k.startswith('_')):
            value = getattr(f, name)
            if value is dataclasses.MISSING:
                value = MISSING
            setattr(new, name, value)
        ftype = f._field_type
        if ftype not in ftypes:
            raise ValueError(f'{cls.__name__}.{f.name} invalid type: {ftype!r}')
        new.field_type = ftypes[ftype]
        converted.append(new)
    return converted

def convert_params(cls):
    """convert dataclass params to the correct-type if a dataclass"""
    from .dataclasses import PARAMS_ATTR
    # ensure type is dataclass or return
    dataclasses = stdlib_dataclasses or sys.modules.get(module_name)
    if not dataclasses:
        return
    if not dataclasses.is_dataclass(cls):
        return
    # just move params attribute
    params = getattr(cls, dataclasses._PARAMS)
    setattr(cls, PARAMS_ATTR, params)

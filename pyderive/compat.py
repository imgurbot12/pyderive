"""
Stdlib Dataclass Compatability Utils
"""
import sys
import importlib
from types import ModuleType
from typing import Optional, Type

from .abc import MISSING, FieldDef, FieldType, Fields

#** Variables **#
__all__ = [
    'monkey_patch', 
    'convert_fields', 
    'convert_params',
    'std_convert_fields',
    'std_convert_dataclass',
]

#: name of stdlib dataclass module
module_name = 'dataclasses'

#: preserved stdlib dataclass module for reference
stdlib_dataclasses: Optional[ModuleType] = None

#** Functions **#

def monkey_patch():
    """
    monkey-patch replace dataclasses w/ pyderive version
    """
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

    :param cls: potential stdlib dataclass object
    :return:    true if cls is stdlib dataclass
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
    """
    convert dataclass params to the correct-type if a dataclass
    
    :param cls: stdlib dataclass to retireve parameters from
    :return:    pyderive dataclass parameters
    """
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

def _import_std_dataclasses():
    """import stdlib dataclasses library"""
    dataclasses = stdlib_dataclasses or sys.modules.get(module_name)
    dataclasses = dataclasses or importlib.import_module(module_name)
    return dataclasses

def std_convert_fields(cls):
    """
    convert pyderive dataclass fields to stdlib dataclass fields

    :param cls: pyderive dataclass
    :return:    stdlib dataclass fields list
    """
    # confirm class is pyderive dataclass
    from .dataclasses import MISSING, is_dataclass, fields
    dataclasses = _import_std_dataclasses()
    if dataclasses.is_dataclass(cls):
        return dataclasses.fields(cls)
    if not is_dataclass(cls):
        raise ValueError(f'{cls!r} is not a pyderive dataclass')
    # generate translation layers
    ftypes = {
        FieldType.STANDARD: dataclasses._FIELD,
        FieldType.INIT_VAR: dataclasses._FIELD_INITVAR,
    }
    ignore = {'anno', 'field_type'}
    def _missing(v):
        return dataclasses.MISSING if v is MISSING else v 
    # convert fields when required
    stdfields = []
    for field in fields(cls):
        # convert remaining attrs not contained in stdlib field into metadata
        metadata = {}
        for name, value in field.__dict__.items():
            if name in ignore or name in dataclasses.Field.__slots__:
                continue
            metadata[name] = value 
        # generate stdfield and add to field definitions
        stdfield = dataclasses.field(
            init=field.init,
            repr=field.repr,
            hash=field.hash,
            compare=field.compare,
            metadata=metadata,
            default=_missing(field.default),
            default_factory=_missing(field.default_factory),
        )
        stdfield.name = field.name
        stdfield.type = field.anno
        stdfield._field_type = ftypes[field.field_type]
        if sys.version_info.minor >= 10:
            stdfield.kw_only = field.kw_only
        stdfields.append(stdfield)
    return stdfields

def std_convert_dataclass(cls):
    """
    convert pyderive dataclass to stdlib dataclass for 3rd party compatability
    
    :param cls: pyderive dataclass
    :return:    stdlib dataclass
    """
    # confirm class is pyderive dataclas
    from .dataclasses import is_dataclass, PARAMS_ATTR
    dataclasses = _import_std_dataclasses()
    if dataclasses.is_dataclass(cls):
        return cls
    if not is_dataclass(cls):
        raise ValueError(f'{cls!r} is not a pyderive dataclass')
    # generate dataclass name/bases/fields
    name   = cls.__name__
    bases  = cls.__mro__
    fields = std_convert_fields(cls)
    attrs  = [(f.name, f.type, f) for f in fields]
    # generate dataclass kwargs based on python version
    params = getattr(cls, PARAMS_ATTR)
    kwargs = {
        'init':        bool(params.init),
        'repr':        bool(params.repr),
        'eq':          params.eq,
        'order':       params.order,
        'unsafe_hash': params.unsafe_hash,
        'frozen':      params.frozen,
    }
    if sys.version_info.minor >= 10:
        kwargs.update({
            'match_args': params.match_args,
            'kw_only':    params.kw_only,
            'slots':      params.slots,
        })
    # finalize dataclass generation
    return dataclasses.make_dataclass(name, attrs, bases=bases, **kwargs)


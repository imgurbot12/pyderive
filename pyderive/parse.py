"""
DataClass Parsing Tools
"""
from typing import Type, Optional, get_origin

from .abc import *

#** Variables **#
__all__ = [
    'DERIVE_ATTR',

    'remove_field',
    'parse_fields',
    'flatten_fields',
]

#: raw field attribute name
DERIVE_ATTR = '__derive__'

#: track hashes of already compiled baseclasses
COMPILED = set()

#** Functions **#

def remove_field(fields: ClassStruct, name: str):
    """
    remove field-name from fields heigharchy
    """
    current: Optional[ClassStruct] = fields
    while current:
        if name in current.fields:
            del current.fields[name]
            current.order.remove(name)
        current = current.parent

def parse_fields(
    cls:     Type,
    factory: Type[FieldDef] = Field,
    recurse: bool           = True, 
    delete:  bool           = True
) -> ClassStruct:
    """
    parse field definitions from class and delete values if allowed

    :param base:    baseclass type to retrieve annotations/values from
    :param factory: field type factory used to produce fields
    :param recurse: enable recursive handling of field parsing if true
    :param delete:  delete values from class when found if true
    :return:        unprocessed dataclass field definitions
    """
    global COMPILED
    bases  = list(cls.__mro__) if recurse else [cls]
    fields = None
    while bases:
        # skip builtin bases
        base = bases.pop()
        if base is object:
            continue
        # skip if recursive and already compiled
        if recurse and hash(base) in COMPILED:
            continue
        COMPILED.add(hash(base))
        # process fields
        parent      = getattr(base, DERIVE_ATTR, None)
        fields      = ClassStruct(parent=parent)
        annotations = getattr(base, '__annotations__', {})
        for name, anno in annotations.items():
            # retrieve default-value of variable (if exists)
            default = getattr(base, name, MISSING)
            if delete and hasattr(base, name):
                delattr(base, name)
            # handle ClassVar
            if get_origin(anno) is ClassVar:
                remove_field(fields, name)
                continue
            # preserve order of fields and add vardef
            if name not in fields.order:
                fields.order.append(name)
            # assign field based on value
            if isinstance(default, FieldDef):
                field      = default
                field.name = name
                field.anno = anno
            else:
                field = factory(name, anno, default)
            # handle InitVar
            if not isinstance(anno, type) and isinstance(anno, InitVar):
                field.anno = anno.type
                field.field_type = FieldType.INIT_VAR 
            fields.fields[name] = field
        # apply fields to baseclass to allow for inheritance
        if fields.fields:
            setattr(base, DERIVE_ATTR, fields)
    # ensure fields were parsed
    if fields is None:
        raise RuntimeError(f'DataClass Field-Parse Failed: {cls!r}')
    # ensure field-attr is set on top-level
    if not hasattr(cls, DERIVE_ATTR):
        setattr(cls, DERIVE_ATTR, fields)
    return fields

def has_default(field: FieldDef) -> bool:
    """return true if field has default"""
    return field.default is not MISSING or field.default_factory is not MISSING

def flatten_fields(
    fields: ClassStruct, order_kw: bool = True) -> Fields:
    """
    flatten field definitions using standard dataclass varaiable flattening

    :param fields:   list of higharchigal field definitions
    :param order_kw: ensure all fields w/o values appear before those that do
    :return:         standard flattened/ordererd field definitions
    """
    # order heigharchy from farthest-parent to class-itself
    heigharchy = [fields]
    while fields.parent:
        fields = fields.parent
        heigharchy.insert(0, fields)
    # sort fields
    struct = FlatStruct()
    kwargs = False # track when kwargs have been spotted
    for fields in heigharchy:
        for name in fields.order:
            field   = fields.fields[name]
            default = has_default(field)
            kwargs  = kwargs or default
            # raise error if non-kwarg found after kwargs start
            if order_kw and kwargs and not default:
                raise TypeError(
                    f'non-default argument {name!r} follows default argument')
            # append vardef to order and set/replace definition
            if name not in struct.fields:
                struct.order.append(name)
            struct.fields[name] = field
    return struct.ordered_fields()

"""
DataClass Parsing Tools
"""
from types import MemberDescriptorType
from typing import Type, Optional, ClassVar, get_origin

from .abc import *
from .compat import is_stddataclass, convert_fields

#** Variables **#
__all__ = [
    'DERIVE_ATTR',

    'remove_field',
    'parse_fields',
    'flatten_fields',
]

#: raw field attribute name
DERIVE_ATTR = '__derive__'

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
    delete:  bool           = True,
    strict:  bool           = True,
) -> ClassStruct:
    """
    parse field definitions from class and delete values if allowed

    :param base:    baseclass type to retrieve annotations/values from
    :param factory: field type factory used to produce fields
    :param recurse: enable recursive handling of field parsing if true
    :param delete:  delete values from class when found if true
    :param strict:  be strict on factory field type during parsing
    :return:        unprocessed dataclass field definitions
    """
    bases  = list(cls.__mro__) if recurse else [cls]
    fields = None
    ftype: Type[FieldDef] = factory if strict else FieldDef
    while bases:
        # skip builtin bases
        base = bases.pop()
        if base is object:
            continue
        # convert stdlib dataclass fields to valid class-struct
        parent = getattr(base, DERIVE_ATTR, None)
        if parent is None and is_stddataclass(base):
            fields = convert_fields(base, ftype)
            names  = [f.name for f in fields]
            parent = ClassStruct(names, {f.name:f for f in fields})
        fields = ClassStruct(parent=parent)
        # check if baseclass is already compiled
        if fields.is_base_compiled(base):
            continue
        # skip evaluations is annotations have already been checked
        annotations = getattr(base, '__annotations__', None) or dict()
        if fields.is_anno_compiled(annotations):
            continue
        # iterate annotations
        for name, anno in annotations.items():
            # handle ClassVar
            if get_origin(anno) is ClassVar:
                remove_field(fields, name)
                continue
            # retrieve default-value of variable (if exists)
            default     = getattr(base, name, MISSING)
            member_desc = isinstance(default, MemberDescriptorType)
            default     = MISSING if member_desc else default
            if delete and hasattr(base, name) and not member_desc:
                delattr(base, name)
            # preserve order of fields and add vardef
            if name not in fields.order:
                fields.order.append(name)
            # assign field based on value
            if isinstance(default, ftype):
                field      = default
                field.name = name
                field.anno = anno
            elif isinstance(default, FieldDef):
                fclass = type(default).__name__
                fallow = ftype.__name__
                raise TypeError(
                    f'unsupported field-type {fclass!r}. must use {fallow!r}')
            else:
                field = factory(name, anno, default)
            # handle InitVar
            inner_anno = get_initvar(anno)
            if inner_anno:
                field.anno = inner_anno
                field.field_type = FieldType.INIT_VAR
            # finalize field build and assign to struct
            field.__compile__(cls)
            fields.fields[name] = field
        # apply fields to baseclass to allow for inheritance
        fields.base        = base
        fields.annotations = annotations
        if fields.fields:
            setattr(base, DERIVE_ATTR, fields)
    # ensure fields were parsed
    if fields is None:
        raise RuntimeError(f'DataClass Field-Parse Failed: {cls!r}')
    # ensure field-attr is set on top-level
    if not hasattr(cls, DERIVE_ATTR):
        setattr(cls, DERIVE_ATTR, fields)
    return fields

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
    kwargs = set() # track when kwargs have been spotted
    for fields in heigharchy:
        for name in fields.order:
            field   = fields.fields[name]
            default = has_default(field)
            missing = name not in struct.fields
            if default and field.init and not field.kw_only:
                kwargs.add(name)
            elif name in kwargs:
                kwargs.remove(name)
            # raise error if non-kwarg found after kwargs start
            kwarg = kwargs and field.init and not field.kw_only
            if order_kw and kwarg and missing and not default:
                raise TypeError(
                    f'non-default argument {name!r} follows default argument')
            # append vardef to order and set/replace definition
            if missing:
                struct.order.append(name)
            struct.fields[name] = field
    return struct.ordered_fields()

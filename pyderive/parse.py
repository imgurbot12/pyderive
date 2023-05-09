"""
DataClass Parsing Tools
"""
from typing import Type, get_origin

from .abc import *

#** Variables **#
__all__ = [
    'remove_field',
    'parse_fields',
    'flatten_fields',
]

#: field attribute name
FIELD_ATTR = '__fields__'

#: track hashes of already compiled baseclasses
COMPILED = set()

#** Functions **#

def remove_field(fields: ClassStruct, name: str):
    """
    remove field-name from fields heigharchy
    """
    current = fields
    while current:
        if name in current.fields:
            del current.fields[name]
            current.order.remove(name)
            current.init.discard(name)
            current.args.discard(name)
        current = current.parent

def parse_fields(
    base: Type, recurse: bool = True, delete: bool = True) -> ClassStruct:
    """
    parse field definitions from class and delete values if allowed

    :param base:    baseclass type to retrieve annotations/values from
    :param recurse: enable recursive handling of field parsing if true
    :param delete:  delete values from class when found if true
    :return:        unprocessed dataclass field definitions
    """
    global COMPILED
    bases  = list(base.__mro__) if recurse else []
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
        parent      = getattr(base, FIELD_ATTR, None)
        fields      = ClassStruct(parent=parent)
        annotations = getattr(base, '__annotations__', {})
        for name, anno in annotations.items():
            # retrieve value of variable (if exists)
            value = getattr(base, name, MISSING)
            if delete and hasattr(base, name):
                delattr(base, name)
            # handle ClassVar
            if get_origin(anno) is ClassVar:
                remove_field(fields, name)
                continue
            # preserve order of fields and add vardef
            if name not in fields.order:
                fields.order.append(name)
            # handle ClassVar
            if not isinstance(anno, type) and isinstance(anno, InitVar):
                anno = anno.type
                fields.init.add(name)
            # handle standard field
            else:
                fields.args.add(name)
            fields.fields[name] = FieldDef(name, anno, value)
        # apply fields to baseclass to allow for inheritance
        if fields.fields:
            setattr(base, FIELD_ATTR, fields)
    # ensure fields were parsed
    if fields is None:
        raise RuntimeError(f'DataClass Field-Parse Failed: {base!r}')
    # ensure field-attr is set on top-level
    if not hasattr(base, FIELD_ATTR):
        setattr(base, FIELD_ATTR, fields)
    return fields

def flatten_fields(
    fields: ClassStruct, order_kw: bool = True) -> FlatStruct:
    """
    flatten field definitions using standard dataclass varaiable flattening

    :param fields:   list of higharchigal field definitions
    :param kw_check: ensure all fields w/o values appear before those that do
    :return:         standard flattened field definitions
    """
    # order heigharchy from farthest-parent to class-itself
    heigharchy = [fields]
    while fields.parent:
        fields = fields.parent
        heigharchy.insert(0, fields)
    # sort fields
    newdef = FlatStruct()
    kwargs = False # track when kwargs have been spotted
    for fields in heigharchy:
        # remove init/args that changed types
        newdef.init -= fields.args
        newdef.args -= fields.init
        # concat init/args field listings
        newdef.init |= fields.init
        newdef.args |= fields.args
        # iterate fields in order
        for name in fields.order:
            vardef = fields.fields[name]
            kwargs = kwargs or vardef.value is not MISSING
            # raise error if non-kwarg found after kwargs start
            if order_kw and kwargs and vardef.value is MISSING:
                raise TypeError(
                    f'non-default argument {name!r} follows default argument')
            # append vardef to order and set/replace definition
            if name not in newdef.fields:
                newdef.order.append(name)
            newdef.fields[name] = vardef
    return newdef

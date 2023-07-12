"""
XML Serializer/Deserializer Utilities
"""
from typing import Any, Type

from pyxml import Element

from .serde import T, RENAME_ATTR, field_dict, skip_field
from ...dataclasses import is_dataclass, fields

#** Variables **#
__all__ = []

#** Functions **#

def to_xml(cls, use_attrs: bool = False, include_types: bool = False) -> Element:
    """
    generate an xml object from the specified dataclass

    :param use_attrs:     use attributes over assigning a new xml element
    :param include_types: include type information on element when created
    :return:              generated xml-tree from dataclass
    """
    if not is_dataclass(cls) or isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    name = type(cls).__name__
    root = Element(name)
    if include_types:
        root.attrib['type'] = name
    _asxml_inner(root, name, cls, 0, 0, use_attrs, include_types)
    return root

def _asxml_inner(
    root:     Element, 
    name:     str, 
    obj:      Any, 
    rec:      int, 
    lvl:      int, 
    attrs:    bool,
    use_type: bool,
):
    """
    inner xml-ify function to convert dataclass fields into dict

    :param root:     root element to append items onto
    :param name:     name of current element
    :param obj:      object being iterated and assigned to xml
    :param rec:      recursion limit (disabled if below or equal to zero)
    :param lvl:      current recursion level
    :param attrs:    use attributes over assigning a new xml element
    :param use_type: include type information on element when created
    """
    # stop recursin after limit
    if rec > 0 and lvl >= rec:
        return obj
    # dataclass
    lvl += 1
    if is_dataclass(obj):
        for f in fields(obj):
            attr  = getattr(obj, f.name)
            name  = f.metadata.get(RENAME_ATTR) or f.name
            if skip_field(f, attr):
                continue
            _asxml_inner(root, name, attr, rec, lvl, attrs, use_type)
        return root 
    # named-tuple
    elif isinstance(obj, tuple) and hasattr(obj, '_fields'):
        elem  = Element(name)
        names = getattr(obj, '_fields')
        for fname, value in zip(names, obj):
            _asxml_inner(elem, fname, value, rec, lvl, attrs, use_type)
        root.append(elem)
    # standard list/tuple
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _asxml_inner(root, name, value, rec, lvl, attrs, use_type)
    elif isinstance(obj, dict):
        elem = Element(name)
        for key, value in obj.items():
            _asxml_inner(elem, str(key), value, rec, lvl, attrs, use_type)
        root.append(elem)
    elif attrs:
        root.attrib[name] = str(obj)
    else:
        attr = {'type': type(obj).__name__} if use_type else {}
        elem = Element.new(name, attr, text=str(obj))
        root.append(elem)

def from_xml(cls: Type[T], root: Element, allow_unused: bool = False, ignore_attrs: bool = True) -> T:
    """

    """
    fdict = field_dict(cls)
    # iterate children to match to fields
    for elem in root.getchildren():
        # ensure tag matches existing field
        if elem.tag not in fdict:
            if allow_unused:
                continue
            raise ValueError(f'{cls.__name__!r} Unexpected Tag: {elem.tag!r}')
        # assign xml
        field = fdict[elem.tag]
        if is_dataclass(field.anno):
            pass

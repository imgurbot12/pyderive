"""
XML Serializer/Deserializer Utilities
"""
from abc import abstractmethod
import importlib
from typing import *
from typing_extensions import get_origin, get_args

from .serde import T, RENAME_ATTR, field_dict, skip_field, is_sequence
from ...dataclasses import is_dataclass, fields

#** Variables **#
__all__ = ['xml_allow_attr', 'to_xml', 'from_xml', 'from_string', 'to_string']

ToStringFunc   = Callable[['Element'], str]
FromStringFunc = Callable[[str], 'Element']

#: types allowed as xml attributes
ALLOWED_ATTRS: Set[Type] = {str, int, float, complex}

#** Functions **#

def find_element() -> Tuple[ToStringFunc, FromStringFunc, Type['Element']]:
    """
    generate new xml element from list of supported libraries
    """
    names = ('pyxml', 'lxml.etree', 'xml.etree.ElementTree')
    for name in names:
        try:
            library = importlib.import_module(name)
            return (library.tostring, library.fromstring, library.Element)
        except ImportError:
            pass
    raise ValueError('No XML Backend Available!')

def xml_allow_attr(t: Type):
    """
    configure xml to allow attribute assignment for the specified type

    :param t: type to allow as attribute
    """
    global ALLOWED_ATTRS
    if not isinstance(t, type):
        raise ValueError(f'Invalid Type: {t!r}')
    ALLOWED_ATTRS.add(t)

def to_xml(cls, use_attrs: bool = False, include_types: bool = False) -> 'Element':
    """
    generate an xml object from the specified dataclass

    :param use_attrs:     use attributes over assigning a new xml element
    :param include_types: include type information on element when created
    :return:              generated xml-tree from dataclass
    """
    if not is_dataclass(cls) or isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    root = ElementFactory(type(cls).__name__)
    _asxml_inner(root, root.tag, cls, 0, 0, use_attrs, include_types)
    return next(iter(root))

def _asxml_inner(
    root:     'Element', 
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
        return
    # dataclass
    lvl += 1
    if is_dataclass(obj):
        elem = ElementFactory(name)
        for f in fields(obj):
            attr  = getattr(obj, f.name)
            name  = f.metadata.get(RENAME_ATTR) or f.name
            if skip_field(f, attr):
                continue
            _asxml_inner(elem, name, attr, rec, lvl, attrs, use_type)
        root.append(elem)
    # named-tuple
    elif isinstance(obj, tuple) and hasattr(obj, '_fields'):
        elem  = ElementFactory(name)
        names = getattr(obj, '_fields')
        for fname, value in zip(names, obj):
            _asxml_inner(elem, fname, value, rec, lvl, attrs, use_type)
        root.append(elem)
    # standard list/tuple
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _asxml_inner(root, name, value, rec, lvl, attrs, use_type)
    elif isinstance(obj, dict):
        elem = ElementFactory(name)
        for key, value in obj.items():
            _asxml_inner(elem, str(key), value, rec, lvl, attrs, use_type)
        root.append(elem)
    elif attrs and type(obj) in ALLOWED_ATTRS:
        root.attrib[name] = str(obj)
    else:
        elem = ElementFactory(name)
        elem.text   = str(obj)
        elem.attrib.update({'type': type(obj).__name__} if use_type else {})
        root.append(elem)

def from_xml(cls: Type[T], 
    root: 'Element', allow_unused: bool = False, use_attrs: bool = False) -> T:
    """
    parse the specified xml element-tree into a valid dataclass object

    :param cls:          dataclass type to generate
    :param root:         root element containing dataclass fields
    :param allow_unused: allow unused and unrecognized element-tags
    :param use_attrs:    use attributes to assign as fields
    :return:             generated dataclass object
    """
    # validate cls is valid dataclass type
    if not is_dataclass(cls) or not isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    # iterate children to match to fields
    fdict  = field_dict(cls)
    kwargs = {}
    for elem in root:
        # ensure tag matches existing field
        if elem.tag not in fdict:
            if allow_unused:
                continue
            raise ValueError(f'{cls.__name__!r} Unexpected Tag: {elem.tag!r}')
        # assign xml according to field annotation
        field = fdict[elem.tag]
        value = _fromxml_inner(field.anno, elem, allow_unused, use_attrs)
        if is_sequence(value):
            kwargs.setdefault(field.name, type(value)())
            kwargs[field.name].extend(value)
        else:
            kwargs[field.name] = value
    # skip attributes if not enabled
    if not use_attrs:
        return cls(**kwargs)
    # iterate attributes to match fields
    for key, value in root.attrib.items():
        field = fdict.get(key)
        if field and field.anno in ALLOWED_ATTRS:
            kwargs[field.name] = field.anno(value)
    return cls(**kwargs)

def _fromxml_inner(anno: Type, elem: 'Element', *args) -> Any:
    """
    parse the specified xml-element to match the given annotation

    :param anno: annotation to parse from element
    :param elem: element being parsed to match annotation
    :param args: additional arguments to pass to parsers
    """
    # handle datacalss
    if is_dataclass(anno):
        return from_xml(anno, elem, *args)
    # handle sequences
    origin = get_origin(anno)
    if origin in (list, tuple, set, Sequence):
        ianno = get_args(anno)[0]
        return origin([_fromxml_inner(ianno, elem, *args)])
    # handle dictionaries
    if origin in (dict, Mapping):
        _, vanno = get_args(anno)
        result   = {}
        for child in elem:
            key   = child.tag
            value = _fromxml_inner(vanno, child, *args)
            result[key] = value
        return origin(result)
    # handle simple string conversion types
    if anno in ALLOWED_ATTRS:
        return anno(elem.text)
    return elem.text

def to_string(cls, **kwargs) -> str:
    """
    convert dataclass to xml string

    :param cls:    dataclass instance
    :param kwargs: additional arguments to pass to xml builder
    :return:       xml string equivalent
    """
    root   = to_xml(cls, **kwargs)
    string = ToString(root)
    return string.decode() if isinstance(string, bytes) else string

def from_string(cls: Type[T], xml: str, **kwargs) -> T:
    """
    convert xml-string into templated dataclass object

    :param cls:    dataclass type to generate
    :param xml:    xml string to parse into dataclass
    :param kwargs: additional arguments to pass to xml parser
    :return:       dataclass instance
    """
    root = FromString(xml)
    return from_xml(cls, root, **kwargs)

#** Classes **#

class Element(Protocol):
    tag:    str
    text:   str
    attrib: Dict[str, Any]

    @abstractmethod
    def __init__(self, tag: str):
        raise NotImplementedError
   
    @abstractmethod
    def __iter__(self) -> Iterator['Element']:
        raise NotImplementedError

    @abstractmethod
    def getchildren(self) -> List['Element']:
        raise NotImplementedError

    @abstractmethod
    def append(self, element: 'Element'):
        raise NotImplementedError

#** Init **#

#: xml element-factory
ToString, FromString, ElementFactory = find_element()

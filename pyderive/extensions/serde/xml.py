"""
XML Serializer/Deserializer Utilities
"""
from abc import abstractmethod
import importlib
from typing import (
    Any, Callable, Dict, Iterator, List, Mapping, Optional,
    Protocol, Sequence, Set, Tuple, Type, Union, cast)
from typing_extensions import get_origin, get_args

from .serde import *
from .serde import RENAME_ATTR, SUPPORTED_TYPES
from ...dataclasses import is_dataclass, fields

#** Variables **#
__all__ = ['xml_allow_attr', 'to_xml', 'from_xml', 'from_string', 'to_string']

ToStringFunc   = Callable[..., str]
FromStringFunc = Callable[[str], 'Element']

#: types allowed as xml attributes
ALLOWED_ATTRS: Set[Type] = {str, bool, int, float, complex}

#** Functions **#

def find_element() -> Tuple[ToStringFunc, FromStringFunc, Type['Element']]:
    """
    generate new xml element from list of supported libraries
    """
    names = ('pyxml', 'lxml.etree', 'xml.etree.ElementTree', )
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

def _is_namedtuple(value: Any) -> bool:
    """return true if value is a named tuple instance"""
    return isinstance(value, tuple) and hasattr(value, '_fields')

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
    elif _is_namedtuple(obj):
        elem  = ElementFactory(name)
        names = getattr(obj, '_fields')
        for fname, value in zip(names, obj):
            _asxml_inner(elem, fname, value, rec, lvl, attrs, use_type)
        root.append(elem)
    # standard list/tuple
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _asxml_inner(root, name, value, rec, lvl, attrs, use_type)
    # dictionary/mapping
    elif isinstance(obj, dict):
        elem = ElementFactory(name)
        for key, value in obj.items():
            _asxml_inner(elem, str(key), value, rec, lvl, attrs, use_type)
        root.append(elem)
    # allowed attributes
    elif attrs and type(obj) in ALLOWED_ATTRS:
        root.attrib[name] = str(obj)
    # default
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
    for pos, elem in enumerate(root, 0):
        # ensure tag matches existing field
        if elem.tag not in fdict:
            if allow_unused:
                continue
            raise ValueError(f'{cls.__name__!r} Unexpected Tag: {elem.tag!r}')
        # assign xml according to field annotation
        field = fdict[elem.tag]
        value = _fromxml_inner(pos, field.anno, elem, (allow_unused, use_attrs))
        if is_sequence(value) and not _is_namedtuple(value):
            kwargs.setdefault(field.name, [])
            kwargs[field.name].extend(value)
        else:
            kwargs[field.name] = value
    # skip attributes if not enabled
    if use_attrs:
        # iterate attributes to match fields
        for key, value in root.attrib.items():
            field = fdict.get(key)
            if field and field.anno in ALLOWED_ATTRS:
                kwargs[field.name] = field.anno(value)
    # map kwargs to the original annotation type when possible
    namedict = {f.name:f for f in fields(cls)}
    for key, value in kwargs.items():
        field  = namedict[key]
        origin = get_origin(field.anno)
        if field.anno in SUPPORTED_TYPES and not isinstance(value, field.anno):
            kwargs[key] = field.anno(value)
        elif origin in SUPPORTED_TYPES and not isinstance(value, origin):
            kwargs[key] = origin(value)
    return cls(**kwargs)

def _fromxml_inner(pos: int, anno: Type, elem: 'Element', args: tuple) -> Any:
    """
    parse the specified xml-element to match the given annotation

    :param pos:  current index of element from parent
    :param anno: annotation to parse from element
    :param elem: element being parsed to match annotation
    :param args: additional arguments to pass to parsers
    """
    # handle datacalss
    if is_dataclass(anno):
        return from_xml(anno, elem, *args)
    # handle named-tuple
    if anno_is_namedtuple(anno):
        # manually collect annotations from named-tuple
        _, vannos = namedtuple_annos(anno)
        result = {}
        for pos, (vanno, child) in enumerate(zip(vannos, elem), 0):
            key   = child.tag
            value = _fromxml_inner(pos, vanno, child, args)
            result[key] = value
        return anno(**result)
    # handle defined unions
    origin = get_origin(anno)
    if origin is Union:
        for subanno in get_args(anno):
            newval = _fromxml_inner(pos, subanno, elem, args)
            if newval != elem.text:
                return newval
    # handle defined sequences
    elif origin in (list, set, Sequence):
        origin = cast(Type[list], list if origin is Sequence else origin)
        ianno  = get_args(anno)[0]
        return origin([_fromxml_inner(pos, ianno, elem, args)])
    # handle defined tuples
    elif origin is tuple:
        iannos = get_args(anno)
        ianno = iannos[pos] if pos < len(iannos) else str
        return (_fromxml_inner(pos, ianno, elem, args), )
    # handle defined dictionaries
    elif origin in (dict, Mapping):
        _, vanno = get_args(anno)
        result   = {}
        for pos, child in enumerate(elem, 0):
            key   = child.tag
            value = _fromxml_inner(pos, vanno, child, args)
            result[key] = value
        return dict(result)
    # handle simple string conversion types
    elif anno in ALLOWED_ATTRS:
        try:
            return anno(elem.text)
        except Exception:
            pass
    return elem.text

def to_string(cls, xml_declaration: Optional[str] = '', **kwargs) -> str:
    """
    convert dataclass to xml string

    :param cls:    dataclass instance
    :param kwargs: additional arguments to pass to xml builder
    :return:       xml string equivalent
    """
    root   = to_xml(cls, **kwargs)
    string = ToString(root, xml_declaration=xml_declaration)
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
    def __len__(self) -> int:
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

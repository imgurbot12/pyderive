"""
Serde Serialization/Deserialization Tools/Baseclasses
"""
import ipaddress
from abc import abstractmethod
from typing import (
    Any, Callable, Dict, List, Mapping, Optional, Protocol,
    Sequence, Set, Tuple, Type, TypeVar, Union, cast)
from typing_extensions import runtime_checkable, get_origin, get_args

from ... import BaseField
from ...abc import MISSING, FieldDef, InitVar, has_default
from ...dataclasses import FIELD_ATTR
from ...dataclasses import *

#** Variables **#
__all__ = [
    'validate_serde',
    'is_serde',
    'T',
    'S',
    'D',
    'SkipFunc',

    'field_dict',
    'skip_field',
    'is_sequence',
    'anno_is_namedtuple',
    'namedtuple_annos',
    'from_sequence',
    'from_mapping',
    'from_object',
    'to_dict',
    'to_tuple',

    'SerdeError',
    'SerdeParseError',
    'UnknownField',
    'SerdeParams',
    'SerdeField',
    'TypeEncoder',
    'TypeDecoder',
    'Serializer',
    'Deserializer',
]

T = TypeVar('T')
S = TypeVar('S', covariant=True)
D = TypeVar('D', contravariant=True)

#: skip function typehint
SkipFunc = Callable[[Any], bool]

#: supported base python types
SUPPORTED_TYPES = [str, bool, int, float, complex, list, tuple, set, frozenset]

#: serde validation tracker
SERDE_PARAMS_ATTR = '__serde_params__'

RENAME_ATTR       = 'serde_rename'
ALIASES_ATTR      = 'serde_aliases'
SKIP_ATTR         = 'serde_skip'
SKIP_IF_ATTR      = 'serde_skip_if'
SKIP_IFFALSE_ATTR = 'serde_skip_if_false'
SKIP_DEFAULT_ATTR = 'serde_skip_default'

#** Functions **#

def validate_serde(cls: Type):
    """
    transform into dataclass and validate serde settings

    :param cls:    base dataclass type
    :param kwargs: additional settings to pass to dataclass generation
    :return:       serde-validated dataclass instance
    """
    # validate fields
    names  = set()
    fields = getattr(cls, FIELD_ATTR)
    for field in fields:
        # validate unique names/aliases
        name = field.name
        newname = field.metadata.get(RENAME_ATTR) or field.name
        if newname in names:
            raise SerdeError(f'rename: {newname!r} already reserved.')
        names.add(newname)
        for alias in field.metadata.get(ALIASES_ATTR, []):
            if alias in names:
                raise SerdeError(f'alias: {alias!r} already reserved.')
            names.add(alias)
        # validate skip settings
        skip         = field.metadata.get(SKIP_ATTR)
        skip_if      = field.metadata.get(SKIP_IF_ATTR)
        skip_if_not  = field.metadata.get(SKIP_IFFALSE_ATTR)
        skip_default = field.metadata.get(SKIP_DEFAULT_ATTR)
        if skip and skip_if:
            raise SerdeError(f'field: {name!r} cannot use skip_if w/ skip')
        if skip and skip_if_not:
            raise SerdeError(f'field: {name!r} cannot use skip_if_false w/ skip')
        if skip and skip_default:
            raise SerdeError(f'field: {name!r} cannot use skip_default w/ skip')
        if not has_default(field) \
            and any((skip, skip_if, skip_if_not, skip_default)):
            raise SerdeError(f'field: {name!r} cannot offer skip w/o default')
    # set/update parameters
    params = getattr(cls, SERDE_PARAMS_ATTR, None) or SerdeParams()
    params.bases.add(cls)
    setattr(cls, SERDE_PARAMS_ATTR, params)

def is_serde(cls) -> bool:
    """
    return true if class has a validated serde-configuration
    """
    params = getattr(cls, SERDE_PARAMS_ATTR, None)
    return params is not None and cls in params.bases

def field_dict(cls) -> Dict[str, FieldDef]:
    """
    retrieve dictionary of valid field definitions
    """
    fdict  = {}
    fields = getattr(cls, FIELD_ATTR)
    for field in fields:
        name = field.metadata.get(RENAME_ATTR) or field.name
        fdict[name] = field
        for alias in field.metadata.get(ALIASES_ATTR, []):
            fdict[alias] = field
    return fdict

def skip_field(field: FieldDef, value: Any) -> bool:
    """
    return true if field should be skipped
    """
    metadata = field.metadata
    if metadata.get(SKIP_ATTR, False):
        return True
    if metadata.get(SKIP_DEFAULT_ATTR, False):
        if field.default is not MISSING:
            return value == field.default
        if field.default_factory is not MISSING:
            return value == field.default_factory() #type: ignore
    skip_if = metadata.get(SKIP_IF_ATTR)
    if skip_if is not None:
        return skip_if(value)
    skip_if_false = metadata.get(SKIP_IFFALSE_ATTR)
    if skip_if_false:
        return not value
    return False

def is_sequence(value: Any) -> bool:
    """
    return true if the given value is a valid sequence
    """
    return isinstance(value, (set, Sequence)) and not isinstance(value, str)

def anno_is_namedtuple(anno) -> bool:
    """
    return true if the given annotation is a named tuple
    """
    return isinstance(anno, type) \
        and issubclass(anno, tuple) \
        and hasattr(anno, '_fields')

def namedtuple_annos(anno: Type) -> Tuple[List[str], Tuple[Type, ...]]:
    """
    retrieve annotations for the given tuple
    """
    fields   = getattr(anno, '_fields')
    annodict = getattr(anno, '__annotations__', {})
    args     = [annodict.get(field, str) for field in fields]
    return (fields, tuple(args))

def _unexpected(name: str, anno: Type, value: Any, path: List[str]):
    """
    raise unexpected type error when parsing objects
    """
    return SerdeParseError(
        f'Field: {name!r} Expected: {anno!r}, Got: {type(value)!r}', path)

def _parse_tuple(
    name:    str,
    anno:    Type,
    names:   Sequence[str],
    args:    Sequence[Type],
    value:   Any,
    decoder: 'TypeDecoder',
    path:    List[str],
    kwargs:  dict
) -> tuple:
    """
    parse tuple value according to annotation

    :param name:    name of object being parsed
    :param anno:    tuple annotation
    :param names:   names of tuple fields
    :param args:    tuple field annotations
    :param value:   tuple object value
    :param decoder: decoder helper implementation
    :param path:    full path of recursive parsing
    :param kwargs:  additional kwargs to pass to recursive function
    :return:        parsed tuple value
    """
    # raise error if value does not match annotation
    if not is_sequence(value):
        raise _unexpected(name, anno, value, path)
    # parse values according
    result = []
    for n, (name, ianno, item) in enumerate(zip(names, args, value), 0):
        item = _parse_object(name, ianno, item,
            decoder, [*path, str(n)], kwargs)
        result.append(item)
    return tuple(result)

def _parse_object(
    name:    str,
    anno:    Type,
    value:   Any,
    decoder: 'TypeDecoder',
    path:    List[str],
    kwargs:  dict
) -> Any:
    """
    recursively parse dataclass annotation

    :param name:    name of object being parsed
    :param anno:    annotation of object being parsed
    :param value:   value of object being parsed
    :param decoder: decoder helper implementation
    :param path:    full path of recursive parsing
    :param kwargs:  additional kwargs to pass to recursive function
    :return:        parsed object value
    """
    # handle dataclass parsing
    if is_dataclass(anno):
        if is_sequence(value):
            return from_sequence(anno, value, decoder, path, **kwargs)
        elif isinstance(value, Mapping):
            return from_mapping(anno, value, decoder, path, **kwargs)
    # handle named-tuples
    if anno_is_namedtuple(anno):
        names, args = namedtuple_annos(anno)
        return _parse_tuple(name, anno, names, args,
                    value, decoder, path, kwargs)
    # handle defined union tpes
    origin = get_origin(anno)
    if origin is Union:
        # check if already a valid type in union
        args = get_args(anno)
        types = tuple(arg for arg in args if isinstance(arg, type))
        if isinstance(value, types):
            return value
        # attempt to convert it w/ parsing
        for subanno in args:
            newval = _parse_object(name, subanno, value, decoder, path, kwargs)
            if newval != value:
                return newval
    # handle defined dictionary types
    elif origin in (dict, Mapping):
        # raise error if value does not match annotation
        if not isinstance(value, (dict, Mapping)):
            raise _unexpected(name, anno, value, path)
        # parse key/value items
        result       = {}
        kname, vname = f'{name}[key]', f'{name}[val]'
        kanno, vanno = get_args(anno)
        for k,v in value.items():
            k = _parse_object(kname, kanno, k, decoder, path, kwargs)
            v = _parse_object(vname, vanno, v, decoder, [*path, k], kwargs)
            result[k] = v
        return type(value)(result) # type: ignore
    # handle defined tuple sequences
    elif origin is tuple:
        # raise error if value does not match annotation
        args  = get_args(anno)
        names = [f'{name}[{n}]' for n in range(0, len(args))]
        return _parse_tuple(name, anno, names, args,
            value, decoder, path, kwargs)
    # handle defined sequence types
    elif origin in (list, set, Sequence):
        oanno = cast(Type[list], list if origin is Sequence else origin)
        # raise error if value does not match annotation
        if not is_sequence(value):
            raise _unexpected(name, anno, value, path)
        # parse sequence items
        ianno  = get_args(anno)[0]
        result = []
        for n, item in enumerate(value, 0):
            item = _parse_object(f'{name}[{n}]', ianno,
                item, decoder, [*path, str(n)], kwargs)
            result.append(item)
        return oanno(result)
    # allow for custom decoding on arbritrary types
    elif value not in SUPPORTED_TYPES:
        return decoder.default(anno, value)
    # allow for typecasting when value type does not match
    elif anno in SUPPORTED_TYPES and type(value) != anno:
        return anno(value)
    return value

def _has_skip(field: FieldDef) -> int:
    """check if field has any skip attribute"""
    if field.metadata.get(SKIP_ATTR, False):
        return -1
    for attr in (SKIP_DEFAULT_ATTR, SKIP_IF_ATTR, SKIP_IFFALSE_ATTR):
        if field.metadata.get(attr, False):
            return 1
    return 2

def from_sequence(
    cls:      Type[T],
    values:   Union[Sequence, Set],
    decoder: 'TypeDecoder',
    path:    Optional[List[str]] = None,
    **kwargs
) -> T:
    """
    parse sequence into a valid dataclasss object

    :param cls:     validation capable dataclass object
    :param values:  sequence to parse into valid dataclass object
    :param decoder: decoder helper used for deserialization
    :param path:    Optional[List[str]] = None,
    :param kwargs:  additional arguments to pass to recursive evaluation
    :return:        parsed dataclass object
    """
    # validate dataclass and serde information
    if not is_dataclass(cls) and not isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    if not is_serde(cls):
        validate_serde(cls)
    # check range of parameters
    path   = path or []
    fields = getattr(cls, FIELD_ATTR)
    if len(values) > len(fields):
        raise SerdeParseError(
            f'{cls.__name__}: sequence contains too many values.', path)
    # limit number of fields to required components
    if len(values) < len(fields):
        required = [f for f in fields if not has_default(f)]
        optional = [(n,f) for n,f in enumerate(fields, 0) if has_default(f)]
        optional.sort(key=lambda f: _has_skip(f[1]), reverse=True)
        while len(required) < len(values):
            pos, field = optional.pop(0)
            required.insert(pos, field)
        fields = required
    # iterate values and try to match to annotations
    attrs = {}
    for field, value in zip(fields, values):
        value = _parse_object(field.name, field.anno,
            value, decoder, [*path, field.name], kwargs)
        if not skip_field(field, value):
            attrs[field.name] = value
    # convert to object, preserve path in error
    try:
        return cls(**attrs)
    except Exception as e:
        if isinstance(e, PathError):
            e.path = [*path, *e.path]
        raise e

def from_mapping(
    cls:      Type[T],
    values:   Mapping,
    decoder: 'TypeDecoder',
    path:    Optional[List[str]] = None,
    *,
    allow_unknown: bool = False,
    **kwargs
) -> T:
    """
    parse mapping into a valid dataclass object

    :param cls:           validation capable dataclass object
    :param values:        sequence to parse into valid dataclass object
    :param decoder:       decoder helper used for deserialization
    :param path:          full path of recursive parsing
    :param allow_unknown: allow for unknown and invalid keys during dict parsing
    :param kwargs:        additional arguments to pass to recursive evaluation
    :return:              parsed dataclass object
    """
    # validate dataclass and serde information
    if not is_dataclass(cls) and not isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    if not is_serde(cls):
        validate_serde(cls)
    # parse key/value into kwargs
    attrs = {}
    path  = path or []
    fdict = field_dict(cls)
    kwargs.setdefault('allow_unknown', allow_unknown)
    for key, value in values.items():
        # handle unexpected keys
        if key not in fdict:
            if allow_unknown:
                continue
            raise UnknownField(key, path)
        # translate value based on annotation
        field = fdict[key]
        name  = field.name
        if skip_field(field, value):
            continue
        attrs[name] = _parse_object(name, field.anno,
            value, decoder, [*path, key], kwargs)
    # convert to object, preserve path in error
    try:
        return cls(**attrs)
    except Exception as e:
        if isinstance(e, PathError):
            e.path = [*path, *e.path]
        raise e

def from_object(cls: Type[T],
    value: Any, decoder: Optional['TypeDecoder'] = None, **kwargs) -> T:
    """
    parse an object into a valid dataclass instance

    :param cls:     validation capable dataclass object
    :param values:  object into valid dataclass object
    :param decoder: decoder helper used for deserialization
    :param kwargs:  additional arguments to pass to recursive evaluation
    :return:        parsed dataclass object
    """
    if not is_dataclass(cls) and not isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    decoder = decoder or TypeDecoder()
    if is_sequence(value):
        return from_sequence(cls, value, decoder, **kwargs)
    elif isinstance(value, Mapping):
        return from_mapping(cls, value, decoder, **kwargs)
    raise TypeError(f'Cannot deconstruct: {value!r}')

def _dict_factory(cls, items: List[Tuple[str, Any]]) -> dict:
    """generate custom dictionary-factory"""
    fdict  = {f.name:f for f in fields(cls)}
    output = {}
    for name, value in items:
        field = fdict[name]
        if skip_field(field, value):
            continue
        name = field.metadata.get(RENAME_ATTR) or name
        output[name] = value
    return output

def _tuple_factory(cls, items: List[Any]) -> tuple:
    """generate custom tuple-factory"""
    output    = []
    fielddefs = fields(cls)
    for field, item in zip(fielddefs, items):
        if skip_field(field, item):
            continue
        output.append(item)
    return tuple(output)

def to_dict(cls, encoder: Optional['TypeEncoder'] = None) -> Dict[str, Any]:
    """
    convert dataclass instance to dictionary following serde skip rules

    :param cls:     dataclass instance to convert to dictionary
    :param encoder: optional encoder instance for encoding objects
    :return:        dictionary representing dataclass object
    """
    if not is_dataclass(cls) or isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    encoder = encoder or TypeEncoder()
    return asdict(cls, encoder=encoder.default, dict_factory=_dict_factory)

def to_tuple(cls, encoder: Optional['TypeEncoder'] = None) -> Tuple:
    """
    convert dataclass instance to tuple following serde skip rules

    :param cls:     dataclass instance to convert to tuple
    :param encoder: optional encoder instance for encoding objects
    :return:        tuple representing dataclass object
    """
    if not is_dataclass(cls) or isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    encoder = encoder or TypeEncoder()
    return astuple(cls, encoder=encoder.default, tuple_factory=_tuple_factory)

#** Classes **#

@runtime_checkable
class PathError(Protocol):
    path: List[str]

class SerdeError(ValueError):
    """Custom ValueError Exception"""
    pass

class SerdeParseError(ValueError, PathError):
    """Custom Conversion Exception"""

    def __init__(self, message: str, path: List[str]):
        self.message = message
        self.path    = path

class UnknownField(SerdeParseError):

    def __init__(self, field: str, path: List[str]):
        self.path    = path
        self.field   = field
        self.message = 'Unknown Field'

@dataclass(slots=True)
class SerdeParams:
    """serde configuration parameters"""
    bases: Set[Type] = field(default_factory=set)

@dataclass
class SerdeField(BaseField):
    """serde dataclass field definition"""
    rename:       InitVar[Optional[str]]       = None
    aliases:      InitVar[Optional[List[str]]] = None
    skip:         InitVar[bool]                = False
    skip_if:      InitVar[Optional[SkipFunc]]  = None
    skip_if_not:  InitVar[bool]                = False
    skip_default: InitVar[bool]                = False

    def __post_init__(self,
        rename, aliases, skip, skip_if, skip_if_not, skip_default):
        self.metadata.update({
            RENAME_ATTR:       rename,
            ALIASES_ATTR:      aliases or [],
            SKIP_ATTR:         skip,
            SKIP_IF_ATTR:      skip_if,
            SKIP_IFFALSE_ATTR: skip_if_not,
            SKIP_DEFAULT_ATTR: skip_default,
        })

class TypeEncoder:
    """Object Type Encoder"""

    def default(self, obj: Any) -> Any:
        """handle common python types"""
        if is_sequence(obj):
            return type(obj)([self.default(v) for v in obj])
        if isinstance(obj, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            return str(obj)
        return obj

class TypeDecoder:
    """Object Type Decoder"""

    def default(self, anno: Type, obj: Any) -> Any:
        """handle common python types"""
        if isinstance(anno, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            return ipaddress.ip_address(anno)
        return obj

class Serializer(Protocol[S]):
    """Serializer Interface Definition"""

    @classmethod
    @abstractmethod
    def serialize(cls, obj: Type, **options) -> S:
        raise NotImplementedError

class Deserializer(Protocol[D]):
    """Deserializer Interface Definition"""

    @classmethod
    @abstractmethod
    def deserialize(cls, obj: Type[T], raw: D, **options) -> T:
        raise NotImplementedError

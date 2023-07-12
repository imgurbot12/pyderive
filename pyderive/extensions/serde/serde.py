"""
Serde Serialization/Deserialization Tools/Baseclasses
"""
from abc import abstractmethod
from typing import *

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
    'from_sequence',
    'from_mapping',
    'from_object',
    'to_dict',
    'to_tuple',

    'SerdeParams',
    'SerdeField',
    'Serializer',
    'Deserializer',
]

T = TypeVar('T')
S = TypeVar('S', covariant=True)
D = TypeVar('D', contravariant=True)

#: skip function typehint
SkipFunc = Callable[[Any], bool]

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
            raise ValueError(f'rename: {newname!r} already reserved.')
        names.add(newname)
        for alias in field.metadata.get(ALIASES_ATTR, []):
            if alias in names:
                raise ValueError(f'alias: {alias!r} already reserved.')
            names.add(alias)
        # validate skip settings
        skip         = field.metadata.get(SKIP_ATTR)
        skip_if      = field.metadata.get(SKIP_IF_ATTR)
        skip_if_not  = field.metadata.get(SKIP_IFFALSE_ATTR)
        skip_default = field.metadata.get(SKIP_DEFAULT_ATTR)
        if skip and skip_if:
            raise ValueError(f'field: {name!r} cannot use skip_if w/ skip')
        if skip and skip_if_not:
            raise ValueError(f'field: {name!r} cannot use skip_if_false w/ skip')
        if skip and skip_default:
            raise ValueError(f'field: {name!r} cannot use skip_default w/ skip')
        if not has_default(field) \
            and any((skip, skip_if, skip_if_not, skip_default)):
            raise ValueError(f'field: {name!r} cannot offer skip w/o default')
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
    """retrieve dictionary of valid field definitions"""
    fdict  = {}
    fields = getattr(cls, FIELD_ATTR) 
    for field in fields:
        name = field.metadata.get(RENAME_ATTR) or field.name 
        fdict[name] = field
        for alias in field.metadata.get(ALIASES_ATTR, []):
            fdict[alias] = field
    return fdict

def skip_field(field: FieldDef, value: Any) -> bool:
    """return true if field should be skipped"""
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
    """return true if the given value is a valid sequence"""
    return isinstance(value, (set, Sequence)) and not isinstance(value, str)

def _parse_object(anno: Type, value: Any, **kwargs) -> Any:
    """recursively parse dataclass annotation"""
    if is_dataclass(anno):
        if is_sequence(value):
            return from_sequence(anno, value, **kwargs)
        elif isinstance(value, Mapping):
            return from_mapping(anno, value, **kwargs)
    return value

def _has_skip(field: FieldDef) -> int:
    """check if field has any skip attribute"""
    if field.metadata.get(SKIP_ATTR, False):
        return -1
    for attr in (SKIP_DEFAULT_ATTR, SKIP_IF_ATTR, SKIP_IFFALSE_ATTR):
        if field.metadata.get(attr, False):
            return 1
    return 2

def from_sequence(cls: Type[T], values: Union[Sequence, Set], **kwargs) -> T:
    """
    parse sequence into a valid dataclasss object

    :param cls:      validation capable dataclass object
    :param values:   sequence to parse into valid dataclass object
    :param kwargs:   additional arguments to pass to recursive evaluation
    :return:         parsed dataclass object
    """
    # validate dataclass and serde information
    if not is_dataclass(cls) and not isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    if not is_serde(cls):
        validate_serde(cls)
    # check range of parameters
    fields = getattr(cls, FIELD_ATTR)
    if len(values) > len(fields):
        raise TypeError(f'{cls.__name__}: sequence contains too many values.')
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
        value = _parse_object(field.anno, value, **kwargs)
        if not skip_field(field, value):
            attrs[field.name] = value
    return cls(**attrs)

def from_mapping(cls: Type[T], 
    values: Mapping, *, allow_unknown: bool = False, **kwargs) -> T:
    """
    parse mapping into a valid dataclass object

    :param cls:           validation capable dataclass object
    :param values:        sequence to parse into valid dataclass object
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
    fdict = field_dict(cls)
    kwargs.setdefault('allow_unknown', allow_unknown)
    for key, value in values.items():
        # handle unexpected keys
        if key not in fdict:
            if allow_unknown:
                continue
            raise KeyError(f'Unknown Key: {key!r}')
        # translate value based on annotation
        field = fdict[key]
        value = _parse_object(field.anno, value, **kwargs)
        if not skip_field(field, value):
            attrs[field.name] = value
    return cls(**attrs)

def from_object(cls: Type[T], value: Any, **kwargs) -> T:
    """
    parse an object into a valid dataclass instance

    :param cls:    validation capable dataclass object
    :param values: object into valid dataclass object
    :param kwargs: additional arguments to pass to recursive evaluation
    :return:       parsed dataclass object
    """
    if not is_dataclass(cls) and not isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    if is_sequence(value):
        return from_sequence(cls, value, **kwargs)
    elif isinstance(value, Mapping):
        return from_mapping(cls, value, **kwargs)
    raise TypeError(f'Cannot deconstruct: {value!r}')

def _get_dataclasses(cls) -> List[Type]:
    """get dataclass instances within self and fields in reverse order"""
    start, final = [cls.__class__], []
    while start:
        item = start.pop(0)
        if not is_dataclass(item):
            continue
        final.insert(0, item)
        for field in fields(item):
            start.append(field.anno)
    return final

def _gen_dict_factory(cls) -> DictFactory:
    """generate custom dictionary-factory"""
    fdict = {f.name:f for f in fields(cls)}
    def factory(items: List[Tuple[str, Any]]) -> Dict:
        output = {}
        for name, value in items:
            if name not in fdict:
                raise KeyError(f'{cls.__name__!r} Unexpected Key: {name!r}')
            field = fdict[name]
            if skip_field(field, value):
                continue
            name = field.metadata.get(RENAME_ATTR) or name
            output[name] = value
        return output
    return factory

def _gen_tuple_factory(cls) -> TupleFactory:
    """generate custom tuple-factory"""
    fielddefs = fields(cls)
    def factory(items: List[Any]) -> Tuple:
        output = []
        for field, item in zip(fielddefs, items):
            if skip_field(field, item):
                continue
            output.append(item)
        return tuple(output)
    return factory

def to_dict(cls) -> Dict[str, Any]:
    """
    convert dataclass instance to dictionary following serde skip rules

    :param cls: dataclass instance to convert to dictionary
    :return:    dictionary representing dataclass object
    """
    if not is_dataclass(cls) or isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    # get flattend list of dataclasses in reverse order of appearance
    # and convert them to custom dictionary factories
    dataclasses = _get_dataclasses(cls)
    factories   = map(_gen_dict_factory, dataclasses)
    def dict_factory(items):
        """iterate factories to parse relevant items"""
        try:
            factory = next(factories)
            return factory(items)
        except StopIteration:
            raise ValueError(f'Unexpected Items: {items!r}') from None
    return asdict(cls, dict_factory=dict_factory)

def to_tuple(cls) -> Tuple:
    """
    convert dataclass instance to tuple following serde skip rules

    :param cls: dataclass instance to convert to tuple
    :return:    tuple representing dataclass object
    """
    if not is_dataclass(cls) or isinstance(cls, type):
        raise TypeError(f'Cannot construct non-dataclass instance!')
    # get flattend list of dataclasses in reverse order of appearance
    # and convert them to custom dictionary factories
    dataclasses = _get_dataclasses(cls)
    factories   = map(_gen_tuple_factory, dataclasses)
    def tuple_factory(items):
        """iterate factories to parse relevant items"""
        try:
            factory = next(factories)
            return factory(items)
        except StopIteration:
            raise ValueError(f'Unexpected Items: {items!r}') from None
    return astuple(cls, tuple_factory=tuple_factory)

#** Classes **#

@dataclass(slots=True)
class SerdeParams:
    """serde configuration parameters"""
    bases: Set[Type] = field(default_factory=set)

@dataclass
class SerdeField(BaseField):
    """serde dataclass field definition"""
    rename:       InitVar[Optional[str]]      = None
    skip:         InitVar[bool]               = False
    skip_if:      InitVar[Optional[SkipFunc]] = None
    skip_if_not:  InitVar[bool]               = False
    skip_default: InitVar[bool]               = False

    def __post_init__(self, rename, skip, skip_if, skip_if_not, skip_default):
        self.metadata.update({
            RENAME_ATTR:       rename,
            SKIP_ATTR:         skip,
            SKIP_IF_ATTR:      skip_if,
            SKIP_IFFALSE_ATTR: skip_if_not,
            SKIP_DEFAULT_ATTR: skip_default,
        })

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

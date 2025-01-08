"""
Rust Serde Inspired Serialization Decorators
"""
from typing import Any, Callable, Dict, Optional, Tuple, Type, TypeVar, Union, overload
from typing_extensions import Self, dataclass_transform
from warnings import warn

from .impl import *
from .serde import *
from ...compile import gen_slots
from ...dataclasses import is_dataclass, dataclass, fields

#** Variables **#
__all__ = [
    'serde',
    'field',
    'serialize',
    'deserialize',
    'register_serial',
    'register_deserial',

    'from_object',
    'to_dict',
    'to_tuple',
    'TypeEncoder',
    'TypeDecoder',
    'Serializer',
    'Deserializer',

    'SerdeError',
    'SerdeParseError',
    'UnknownField',

    'Serde',
    'Serialize',
    'Deserialize',
]

#: global registry of supported serializer formats
SERIALIZER_IMPL: Dict[str, Serializer] = {
    'json': JsonSerial,
    'yml':  YamlSerial,
    'yaml': YamlSerial,
    'toml': TomlSerial,
    'xml':  XmlSerial,
}

#: global registry of supported deserializer formats
DESERIALIZER_IMPL: Dict[str, Deserializer] = {
    'json': JsonDeserial,
    'yml':  YamlDeserial,
    'yaml': YamlDeserial,
    'toml': TomlDeserial,
    'xml':  XmlDeserial,
}

C = TypeVar('C', bound=Type)

#** Functions **#

@overload
def serde(cls: None = None, **kwargs) -> Callable[[C], C]:
    ...

@overload
def serde(cls: C, **kwargs) -> C:
    ...

@dataclass_transform()
def serde(cls: Optional[C] = None, **kwargs) -> Union[C, Callable[[C], C]]:
    """
    make dataclass and validate serde settings

    :param cls:    dataclass basetype
    :param kwargs: additional settings to pass during dataclass generation
    :return:       dataclass/serde-supported object
    """
    def wrapper(cls):
        # transform into a dataclass if not already
        if not is_dataclass(cls):
            kwargs.setdefault('slots', True)
            cls = dataclass(cls, **kwargs) #type: ignore
        # validate serde-fields
        validate_serde(cls)
        return cls
    return wrapper if cls is None else wrapper(cls)

def field(**kwargs) -> Any:
    """
    custom pyserde extended field definition

    :param kwargs: args to pass to field definition
    :return:       custom serde field definition
    """
    return SerdeField(**kwargs)

@overload
def serialize(cls,
    format: None = None, *, serial: Serializer[T], **kwargs) -> T:
    ...

@overload
def serialize(cls,
    format: str, serial: None = None, **kwargs) -> Union[str, bytes]:
    ...

def serialize(cls, format: Optional[str] = None,
    serial: Optional[Serializer[T]] = None, **kwargs) -> Union[T, str, bytes]:
    """
    encode the specified dataclass w/ the given format or serializer

    :param cls:    serde compatable dataclass object
    :param format: serializer format name
    :param serial: serialzer implementation to use
    :param kwargs: additional args to pass to serializer
    """
    assert format or serial, 'format or serializer-impl must be specified'
    serial = SERIALIZER_IMPL.get(format) if format else serial
    if serial is None:
        raise ValueError(f'Unsupported Serializer Format: {format!r}')
    return serial.serialize(cls, **kwargs)

@overload
def deserialize(cls: Type[T],
    raw: D, format: None = None, *, deserial: Deserializer[D], **kwargs) -> T:
    ...

@overload
def deserialize(cls: Type[T],
    raw: Union[str, bytes], format: str, deserial: None = None, **kwargs) -> T:
    ...

def deserialize(cls: Type[T],
    raw:      Union[S, str, bytes],
    format:   Optional[str] = None,
    deserial: Optional[Deserializer[S]] = None,
    **kwargs
) -> T:
    """
    decode the specified dataclass w/ the given format or deserializer

    :param cls:      serde compatable dataclass object
    :param raw:      raw content to deserialize
    :param format:   deserializer format name
    :param deserial: deserialzer implementation to use
    :param kwargs:   additional args to pass to serializer
    """
    assert format or deserial, 'format or deserializer-impl must be specified'
    deserial = DESERIALIZER_IMPL.get(format) if format else deserial
    if deserial is None:
        raise ValueError(f'Unsupported Deserializer Format: {format!r}')
    return deserial.deserialize(cls, raw, **kwargs) #type: ignore

def register_serial(name: str, serial: Serializer):
    """
    register serializer w/ the specified name

    :param name:   name of serializer to register
    :param serial: serializer implementation
    """
    global SERIALIZER_IMPL
    if name in SERIALIZER_IMPL:
        warn(f'Serializer: {name!r} already registered. Replacing it!')
    SERIALIZER_IMPL[name] = serial

def register_deserial(name: str, deserial: Deserializer):
    """
    register serializer w/ the specified name

    :param name:     name of serializer to register
    :param deserial: serializer implementation
    """
    global DESERIALIZER_IMPL
    if name in DESERIALIZER_IMPL:
        warn(f'Deserializer: {name!r} already registered. Replacing it!')
    DESERIALIZER_IMPL[name] = deserial

def _init_subclass(cls, slots: bool = True, **kwargs):
    """initialze subclass w/ the specified settings"""
    # skip evaluation if already serde-ified
    if is_serde(cls):
        return
    # add serde verification and set slots
    dataclass(cls, slots=False, **kwargs)
    serde(cls)
    if slots:
        setattr(cls, '__slots__', gen_slots(cls, fields(cls)))
    # run init-subclass for next item in mro
    previous = cls.__mro__[1]
    if hasattr(previous, '__init_subclass__'):
        previous.__init_subclass__(**kwargs)

#** Classes **#

@dataclass_transform()
class Serialize:
    """Implement Serialize Methods on Class Instance"""

    def __init_subclass__(cls, **kwargs):
        _init_subclass(cls, **kwargs)

    def asdict(self, **kwargs) -> Dict[str, Any]:
        """
        convert instance to dictionary

        :return: dictionary of original object
        """
        return to_dict(self, **kwargs)

    def astuple(self, **kwargs) -> Tuple:
        """
        convert instance to tuple

        :return: tuple of orignal object
        """
        return to_tuple(self, **kwargs)

    def serialize(self, *args, **kwargs):
        """
        serialize self w/ the following arguments

        :param args:   positional args to pass to serializer
        :param kwargs: keyword args to pass to serializer
        :return:       encoded version of self
        """
        if not is_serde(self.__class__):
            serde(self.__class__)
        return serialize(self, *args, **kwargs)

    def to_json(self, **kwargs) -> str:
        """
        serialize self as json dictionary

        :return: dataclass encoded as json string
        """
        return self.serialize('json', **kwargs)

    def to_yaml(self, **kwargs) -> str:
        """
        serialize self as yaml object

        :return: dataclass encoded as yaml string
        """
        return self.serialize('yaml', **kwargs)

    def to_toml(self, **kwargs) -> str:
        """
        serialize self as toml object

        :return: dataclass encoded as toml string
        """
        return self.serialize('toml', **kwargs)

    def to_xml(self, **kwargs) -> str:
        """
        serialize self as xml object

        :return: dataclass encoded as xml string
        """
        return self.serialize('xml', **kwargs)

    def write_file(self, path: str, format: Optional[str] = None, **kwargs):
        """
        serialize and write contents to the specified filepath

        :param path:   filepath to write to
        :param format: serializer format to use
        :param kwargs: additional configuration for serialization
        """
        format = format if format else path.rsplit('.', 1)[-1]
        result = self.serialize(format, **kwargs)
        with open(path, 'r') as f:
            f.write(result)

@dataclass_transform()
class Deserialize:
    """Implement Deserialize Methods on Class Instance"""

    def __init_subclass__(cls, **kwargs):
        _init_subclass(cls, **kwargs)

    @classmethod
    def from_object(cls, obj: Any, **kwargs) -> Self:
        """
        parse the specified python object into dataclass

        :param obj: python object to parse into dataclass
        :return:    additional arguments to pass to parser
        """
        return from_object(cls, obj, **kwargs)

    @classmethod
    def deserialize(cls, *args, **kwargs) -> Self:
        """
        deserialize self w/ the following arguments

        :param args:   positional args to pass to deserializer
        :param kwargs: keyword args to pass to deserializer
        :return:       deserialized instance of self
        """
        if not is_serde(cls):
            serde(cls)
        return deserialize(cls, *args, **kwargs)

    @classmethod
    def from_json(cls, json: Union[str, bytes], **kwargs) -> Self:
        """
        deserialize self from json string

        :return: decoded dataclass object
        """
        return cls.deserialize(json, 'json', **kwargs)

    @classmethod
    def from_yaml(cls, yaml: Union[str, bytes], **kwargs) -> Self:
        """
        deserialize self from yaml string

        :return: decoded dataclass object
        """
        return cls.deserialize(yaml, 'yaml', **kwargs)

    @classmethod
    def from_toml(cls, toml: Union[str, bytes], **kwargs) -> Self:
        """
        deserialize self from toml string

        :return: decoded dataclass object
        """
        return cls.deserialize(toml, 'toml', **kwargs)

    @classmethod
    def from_xml(cls, toml: Union[str, bytes], **kwargs) -> Self:
        """
        deserialize self from xml string

        :return: decoded dataclass object
        """
        return cls.deserialize(toml, 'xml', **kwargs)

    @classmethod
    def read_file(cls,
        path: str, format: Optional[str] = None, **kwargs) -> Self:
        """
        read and deserialize contents from the specified filepath

        :param path:   filepath to read from
        :param format: deserializer format to use
        :param kwargs: additonal configuration for deserialization
        :return:       decoded dataclass object
        """
        format = format if format else path.rsplit('.', 1)[-1]
        with open(path, 'rb') as f:
            return cls.deserialize(f.read(), format, **kwargs)

@dataclass_transform()
class Serde(Serialize, Deserialize):
    """Implement Both Serialize/Deserialize Methods on Class Instance"""

    def __init_subclass__(cls, **kwargs):
        _init_subclass(cls, **kwargs)

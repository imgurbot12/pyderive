"""
Serializer/Deserialzer Implementations
"""
import json
from functools import lru_cache
from typing import Type

from .serde import *

#** Variables **#
__all__ = [
    'JsonSerial',
    'YamlSerial',
    'TomlSerial',
    'XmlSerial',
    'JsonDeserial',
    'YamlDeserial',
    'TomlDeserial',
    'XmlDeserial',
]

#** Functions **#

def get_serial_kwargs(kwargs: dict) -> dict:
    """pop object encoding kwargs from dict"""
    keys = ('encoder', )
    args = {}
    for key in keys:
        if key in kwargs:
            args[key] = kwargs.pop(key)
    return args

def get_deserial_kwargs(kwargs: dict) -> dict:
    """pop object parsing kwargs from dict"""
    keys = ('allow_unknown', 'decoder')
    args = {}
    for key in keys:
        if key in kwargs:
            args[key] = kwargs.pop(key)
    return args

#** Classes **#

class JsonSerial(Serializer[str]):
    """"""

    @classmethod
    def serialize(cls, obj: Type, **options) -> str:
        kwargs = get_serial_kwargs(options)
        return json.dumps(to_dict(obj, **kwargs), **options)

class JsonDeserial(Deserializer[str]):
    """"""

    @classmethod
    def deserialize(cls, obj: Type[T], raw: str, **options) -> T:
        kwargs = get_deserial_kwargs(options)
        return from_object(obj, json.loads(raw, **options), **kwargs)

class YamlSerial(Serializer[str]):
    """"""

    @classmethod
    def serialize_tuple(cls, dumper, tup):
        """serialize named-tuples properly"""
        return dumper.represent_list(tup)

    @classmethod
    @lru_cache(maxsize=None)
    def import_yaml(cls):
        import yaml
        yaml.SafeDumper.yaml_multi_representers[tuple] = cls.serialize_tuple
        return yaml

    @classmethod
    def serialize(cls, obj: Type, **options) -> str:
        yaml   = cls.import_yaml()
        kwargs = get_serial_kwargs(options)
        return yaml.safe_dump(to_dict(obj, **kwargs), **options)

class YamlDeserial(Deserializer[str]):
    """"""

    @classmethod
    def deserialize(cls, obj: Type[T], raw: str, **options) -> T:
        import yaml
        kwargs = get_deserial_kwargs(options)
        return from_object(obj, yaml.safe_load(raw, **options), **kwargs)

class TomlSerial(Serializer[str]):
    """"""

    @classmethod
    def serialize(cls, obj: Type, **options) -> str:
        import toml
        kwargs = get_serial_kwargs(options)
        return toml.dumps(to_dict(obj, **kwargs), **options)

class TomlDeserial(Deserializer[str]):
    """"""

    @classmethod
    def deserialize(cls, obj: Type[T], raw: str, **options) -> T:
        import toml
        kwargs = get_deserial_kwargs(options)
        return from_object(obj, toml.loads(raw, **options), **kwargs)

class XmlSerial(Serializer[str]):
    """"""

    @classmethod
    def serialize(cls, obj: Type, **options) -> str:
        from . import xml
        return xml.to_string(obj, **options)

class XmlDeserial(Deserializer[str]):
    """"""

    @classmethod
    def deserialize(cls, obj: Type[T], raw: str, **options) -> T:
        from . import xml
        return xml.from_string(obj, raw, **options)

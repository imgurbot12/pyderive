"""
Serializer/Deserialzer Implementations
"""
import json
from typing import Type

from .serde import T, Serializer, Deserializer, from_object, to_dict

#** Variables **#
__all__ = [
    'JsonSerial', 
    'YamlSerial',
    'TomlSerial',
    'JsonDeserial',
    'YamlDeserial',
    'TomlDeserial',
]

#** Functions **#

def get_object_kwargs(kwargs: dict) -> dict:
    """pop object parsing kwargs from dict"""
    keys = ('allow_unknown', )
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
        return json.dumps(to_dict(obj), **options)

class JsonDeserial(Deserializer[str]):
    """"""

    @classmethod
    def deserialize(cls, obj: Type[T], raw: str, **options) -> T:
        kwargs = get_object_kwargs(options)
        return from_object(obj, json.loads(raw, **options), **kwargs)

class YamlSerial(Serializer[str]):
    """"""

    @classmethod
    def serialize(cls, obj: Type, **options) -> str:
        import yaml
        return yaml.safe_dump(to_dict(obj), **options)

class YamlDeserial(Deserializer[str]):
    """"""

    @classmethod
    def deserialize(cls, obj: Type[T], raw: str, **options) -> T:
        import yaml
        kwargs = get_object_kwargs(options)
        return from_object(obj, yaml.safe_load(raw, **options), **kwargs)

class TomlSerial(Serializer[str]):
    """"""

    @classmethod
    def serialize(cls, obj: Type, **options) -> str:
        import toml
        return toml.dumps(to_dict(obj), **options)

class TomlDeserial(Deserializer[str]):
    """"""

    @classmethod
    def deserialize(cls, obj: Type[T], raw: str, **options) -> T:
        import toml
        kwargs = get_object_kwargs(options)
        return from_object(obj, toml.loads(raw, **options), **kwargs)

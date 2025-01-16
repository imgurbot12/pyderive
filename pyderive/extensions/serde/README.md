Serde DataClass Extension
--------------------------

DataClass Serializer Library Inspired by Rust-Lang's Serde Library.

### Examples

Simple Serialization/Deserialization

```python
from pyderive import dataclass
from pyderive.extensions.serde import *

@serde
@dataclass(slots=True)
class Foo:
  a: int
  b: float
  c: bool
  d: str

foo  = Foo(1, 2.2, True, 'example text')
json = serialize(foo, 'json')

newfoo = deserialize(Foo, json, 'json')

print(foo)
print(json)
print(newfoo)
print(foo == newfoo)
```

Wide Variety of Available Formats

```python
from typing import List
from pyderive.extensions.serde import *

@serde(slots=True) # converts to dataclass if not already
class Foo:
  a: int
  b: List[str]

foo = Foo(1, ['a', 'b', 'c', 'd'])
print('foo', foo)

# bultin support for json/yaml/toml/xml
for fmt in ('json', 'yaml', 'toml', 'xml'):
  content = serialize(foo, fmt)
  print(f'serialized as {fmt}:\n"""\n{content}\n"""')
  new_foo = deserialize(Foo, content, fmt)
  print('deserialized', new_foo, foo == new_foo, '\n')
```

Metaclass Options instead of Decorators

```python
from pyderive.extensions.serde import *

class Foo(Serde):
  a: int
  b: float
  c: bool

class Bar(Serialize):
  a: int
  b: float
  c: bool

class Baz(Deserialize):
  a: int
  b: float
  c: bool

foo      = Foo(1, 2.2, False)
bar      = Foo(1, 2.2, False)
foo_json = foo.to_json()
bar_json = bar.to_json()
baz      = Baz.from_json(bar_json)

print(foo)
print(bar)
print(baz)
print(foo_json)
print(bar_json)
print(foo_json == bar_json)
print(foo == baz)
```

Custom Serializer/Deserializers

```python
from typing import Type, TypeVar
from pyderive.extensions.serde import *

class CustomSerial(Serializer[str]):

    @classmethod
    def serialize(cls, obj: Type, **options) -> str:
        objdict = to_dict(obj)
        return ','.join(f'{k}:{type(v).__name__}/{v}' for k,v in objdict.items())

T = TypeVar('T')

class CustomDeserial(Deserializer[str]):
    TYPES = {'str': str, 'int': int, 'bool': bool}

    @classmethod
    def deserialize(cls, obj: Type[T], raw: str, **options) -> T:
        kwargs = {}
        for item in raw.split(','):
            key, item  = item.split(':', 1)
            typ, value = item.split('/', 1)
            tclass     = cls.TYPES[typ]
            kwargs[key] = tclass(value)
        return obj(**kwargs)

@serde
class Foo:
    a: int
    b: str
    c: bool

foo = Foo(1, 'example', False)

# pass custom serializer/deserializer directly to function
content = serialize(foo, serial=CustomSerial)
newfoo = deserialize(Foo, content, deserial=CustomDeserial)
print(content)
print(newfoo)

# register serializer/deserializer w/ system globaly
register_serial('custom', CustomSerial)
register_deserial('custom', CustomDeserial)
print('==')

# use newly registered serializer/deserializer
content = serialize(foo, 'custom')
newfoo  = deserialize(Foo, content, 'custom')
print(content)
print(newfoo)
```

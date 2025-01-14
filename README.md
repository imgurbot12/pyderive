pyderive
---------

[![PyPI version](https://img.shields.io/pypi/v/pyderive3?style=for-the-badge)](https://pypi.org/project/pyderive3/)
[![Python versions](https://img.shields.io/pypi/pyversions/pyderive3?style=for-the-badge)](https://pypi.org/project/pyderive3/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://github.com/imgurbot12/pyderive/blob/master/LICENSE)
[![Made with Love](https://img.shields.io/badge/built%20with-%E2%99%A5-orange?style=for-the-badge)](https://github.com/imgurbot12/pyderive)

Python3 Custom Dataclass Helpers

### Installation

```bash
pip install pyderive3
```

### Features

Additional Features availalbe via [Extensions](./pyderive/extensions/README.md).

##### Expanded Reimplementation of Dataclasses

###### Default Standards Implemented

_'slots' kwarg now supported in older versions of python such as 3.8_

```python
from pyderive import *

@dataclass
class Foo:
    bar: int

@dataclass(slots=True, order=True)
class Bar(Foo):
    foo: str

bar = Bar(foo='foo', bar=100)
print(asdict(bar))
```

###### Recursive Field Compilation

```python
from pyderive import *
from typing import Optional

class Foo:
    bar: int

@dataclass(recurse=True)
class Bar(Foo):
    foo: Optional[str] = None

bar = Bar(foo='foo', bar=100)
print(bar)
```

###### Allow for Custom Field Definitions

```python
from pyderive import *
from typing import Any

@dataclass
class NewField(BaseField):
    custom_attr: bool = False

def field(*_, **kwargs) -> Any:
    return NewField(**kwargs)

@dataclass(field=NewField)
class Foo:
    a: int
    b: str = field(default='b', repr=False, custom_attr=True)

foo = Foo(1, 'boo')
print(foo)

for f in fields(foo):
    print(f.name, f.custom_attr)
```

###### Backwards Compatibility
```python
import pyderive
import dataclasses

@dataclasses.dataclass
class Foo:
    a: int
    b: int = dataclasses.field(repr=False)

@pyderive.dataclass
class Bar(Foo):
    c: int = pyderive.field(frozen=True)

f = Bar(1, 2, 3)
print(f)
```

###### Monkey Patching

```python
from pyderive import compat
compat.monkey_patch()

from dataclasses import dataclass, field

@dataclass
class Foo:
    a: int
    b: int = field(frozen=True)

f = Foo(1, 2)
print(f)
```

##### Low Level Dataclass Compilation Tools

```python
from pyderive import *

class Foo:
    foo: int

class Bar(Foo):
    bar: int = 100

# parse class-structure into raw unordered heigharhcy
struct = parse_fields(Bar, recurse=True)
print('struct', struct)

# order and structure fields into organized list following dataclass standard
fields = flatten_fields(struct)
print('final_fields', fields)

# build and assign `init` and `repr` functions to `Bar` class
assign_func(Bar, create_init(fields))
assign_func(Bar, create_repr(fields))

# assign slots for field definitions onto `Bar` class
Bar = add_slots(Bar, fields)
print(Bar.__slots__)

# initialize foo w/ compiled `init` func and print w/ added `repr`
bar = Bar(foo=1, bar=2)
print(bar)
```

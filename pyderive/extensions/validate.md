Validation DataClass Extension
-------------------------------

DataClass Validation Library Inspired by PyDantic.

### Examples

Simple Field Validation

```python
from pyderive import dataclass
from pyderive.extensions.validate import *

@validate
@dataclass(slots=True)
class Foo:
    a: int
    b: bool

# no error since values match types
foo = Foo(1, True)
print(foo)

# raises error since value does not match
foo2 = Foo('1', True)
```

MetaClass Option over Decorators

```python
from typing import Dict
from pyderive.extensions.validate import *

class Foo(BaseModel):
    a: IPvAnyAddress
    b: Dict[str, int]

# no error since values match types
foo = Foo('1.1.1.1', {'k1': 1, 'k2': 2})
print(foo)

# builtin object parsing helpers
foo2 = Foo.parse_obj({'a': '1.1.1.1', 'b': {'k1': 1, 'k2': 2}})
print(foo2, foo == foo2)

# raises error w/ invalid ip-address string
foo3 = Foo.parse_obj({'a': '1.1.1', 'b': {'k1': 1, 'k2': 2}})
```

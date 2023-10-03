## Validation DataClass Extension

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

Custom Validators

```python
from pyderive.extensions.validate import *
from typing_extensions import Annotated

def str_validator(value: str) -> str:
    if value == 'example':
        raise ValueError('Cannot use Example!')
    return value

def custom_validator(value: 'CustomType') -> 'CustomType':
    if not isinstance(value.a, str):
        raise ValueError('CustomType.a must be a string!')
    return value

class CustomType:
    def __init__(self, a: str):
        self.a = a

@validate(slots=True) # make dataclass if not already
class Foo:
    a: int
    b: CustomType
    # add validator via the `Annotated` type
    c: Annotated[str, Validator[str_validator]]

foo = Foo(1, CustomType('ok'), 'test')

# register validator for specific type
register_validator(CustomType, custom_validator)

# raises error w/ custom validators
foo2 = Foo(1, CustomType('ok'), 'example')
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

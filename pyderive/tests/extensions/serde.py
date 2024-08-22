"""
PyDerive Validation Extension UnitTests
"""
from typing import Any, Dict, List, NamedTuple, Tuple, Union
from unittest import TestCase

from ...extensions.serde import *

#** Variables **#
__all__ = ['SerdeTests']

#** Classes **#

class SerdeTests(TestCase):
    """Serde Serialization UnitTests"""

    def assertDict(self, s: Any, v: Dict):
        """assert serialization/deserialization for dict works as intended"""
        self.assertEqual(to_dict(s), v)
        self.assertEqual(from_object(s.__class__, v), s)

    def assertTuple(self, s: Any, v: Tuple):
        """assert serialization/deserialization for tuple works as intended"""
        self.assertEqual(to_tuple(s), v)
        self.assertEqual(from_object(s.__class__, v), s)

    def assertSerial(self, serde: Any, format: str, value: str):
        """assert serialization/deserialization for value works as intended"""
        self.assertEqual(serialize(serde, format), value)
        self.assertEqual(deserialize(serde.__class__, value, format), serde)

    def test_toobject(self):
        """ensure basic `to_dict` and `to_tuple` works as intended"""
        @serde
        class Bar:
            x: int = 3
            y: int = 4
        @serde
        class Foo:
            a:   int = 1
            b:   str = 'text'
            bar: Bar = field(default_factory=Bar)
        foo = Foo()
        self.assertDict(foo, {'a': 1, 'b': 'text', 'bar': {'x': 3, 'y': 4}})
        self.assertTuple(foo, (1, 'text', (3, 4)))

    def test_serialize(self):
        """ensure basic `serialize` functions works as intended"""
        @serde
        class Foo:
            a: int
            b: str
        foo = Foo(1, 'text')
        self.assertSerial(foo, 'json', '{"a": 1, "b": "text"}')
        self.assertSerial(foo, 'yaml', 'a: 1\nb: text\n')
        self.assertSerial(foo, 'toml', 'a = 1\nb = "text"\n')
        self.assertSerial(foo, 'xml', "<Foo><a>1</a><b>text</b></Foo>")

    def test_serialize_complex(self):
        """ensure more complex serialization functions work as intended"""
        class Bar(Serde):
            plot:  Dict[str, int]
            scale: List[float]
        class Bax(NamedTuple):
            a: int
        class Baz(NamedTuple):
            x: int
            y: Union[int, float, Bax]
        class Foo(Serde):
            data: Tuple[bool, float, Baz]
            bars: Dict[str, Bar]
            tups: List[Baz]
        bar1 = Bar({'a': 1, 'b': 2}, [1.1, 2.2])
        bar2 = Bar({'c': 3, 'd': 4}, [3.3, 4.4])
        foo  = Foo((True, 6.9, Baz(1, 2)), {'bar1': bar1, 'bar2': bar2}, [Baz(3, 4.1), Baz(5, Bax(9))])
        dfoo = foo.asdict()
        tfoo = foo.astuple()
        fooj = foo.to_json()
        fooy = foo.to_yaml()
        foox = foo.to_xml()
        self.assertEqual(Foo.from_object(dfoo), foo)
        self.assertEqual(Foo.from_object(tfoo), foo)
        self.assertEqual(Foo.from_json(fooj), foo)
        self.assertEqual(Foo.from_yaml(fooy), foo)
        self.assertEqual(Foo.from_xml(foox), foo)

    def test_rename(self):
        """ensure `rename` field option works as intended"""
        class Foo(Serialize):
            a: int = field(rename='b')
            c: str = 'text'
        foo = Foo(10)
        self.assertDict(foo, {'b': 10, 'c': 'text'})
        self.assertTuple(foo, (10, 'text'))

    def test_skip(self):
        """ensure `skip` field option works as intended"""
        class Foo:
            a: int = field(skip=True)
        class Bar(Serialize):
            a: int   = 10
            b: str   = field(default='text', skip=True)
            c: float = 1.1
        bar = Bar(77)
        self.assertRaises(ValueError, serde, Foo)
        self.assertDict(bar, {'a': 77, 'c': 1.1})
        self.assertTuple(bar, (77, 1.1))

    def test_skip_if(self):
        """ensure `skip_if` field option works as intended"""
        class Foo:
            a: int = field(skip_if=lambda a: a == 1)
        class Bar(Serialize):
            a: int   = field(default=2, skip_if=lambda a: a == 1)
            b: str   = 'text'
            c: float = 1.1
        # serializer tests
        bar = Bar(1)
        self.assertRaises(ValueError, serde, Foo)
        self.assertEqual(to_dict(bar), {'b': 'text', 'c': 1.1})
        self.assertEqual(to_tuple(bar), ('text', 1.1))
        bar = Bar()
        self.assertEqual(bar.asdict(), {'a': 2, 'b': 'text', 'c': 1.1})
        self.assertEqual(bar.astuple(), (2, 'text', 1.1))
        # deserializer tests
        self.assertEqual(from_object(Bar, {'a': 1, 'b': 'text', 'c': 1.1}), bar)
        self.assertEqual(from_object(Bar, (1, 'text', 1.1)), bar)
        self.assertEqual(from_object(Bar, ('text', 1.1)), bar)

    def test_skip_if_not(self):
        """ensure `skip_if_not` field option works as intended"""
        class Foo:
            a: int = field(skip_if_not=True)
        class Bar(Serialize):
            a: int   = 0
            b: str   = 'text'
            c: float = field(default=1.1, skip_if_not=True)
        # serializer tests
        bar = Bar(1, 'ok', 0)
        self.assertRaises(ValueError, serde, Foo)
        self.assertEqual(to_dict(bar), {'a': 1, 'b': 'ok'})
        self.assertEqual(to_tuple(bar), (1, 'ok'))
        bar = Bar()
        self.assertEqual(bar.asdict(), {'a': 0, 'b': 'text', 'c': 1.1})
        self.assertEqual(bar.astuple(), (0, 'text', 1.1))
        # deserializer tests
        self.assertEqual(from_object(Bar, {'a': 0, 'b': 'text', 'c': 0}), bar)
        self.assertEqual(from_object(Bar, (0, 'text', 0)), bar)

    def test_skip_default(self):
        """ensure `skip_default` field option works as intended"""
        class Foo:
            a: int = field(skip_default=True)
        class Bar(Serialize):
            a: str       = 'text'
            b: int       = field(default=10, skip_default=True)
            c: List[str] = field(default_factory=list, skip_default=True)
        bar = Bar('ok')
        self.assertRaises(ValueError, serde, Foo)
        self.assertEqual(to_dict(bar), {'a': 'ok'})
        self.assertEqual(to_tuple(bar), ('ok', ))
        bar = Bar('ok', 11, ['a', 'b'])
        self.assertDict(bar, {'a': 'ok', 'b': 11, 'c': ['a', 'b']})
        self.assertTuple(bar, ('ok', 11, ['a', 'b']))

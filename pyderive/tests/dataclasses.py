"""
PyDerive DataClass UnitTests
"""
import unittest
import dataclasses
from typing import ClassVar, List, Optional

from ..dataclasses import *

#** Variables **#
__all__ = ['DataClassTests']

#** Classes **#

class DataClassTests(unittest.TestCase):

    def test_repr_standard(self):
        """ensure standard repr works as intended"""
        @dataclass
        class Foo:
            a: int
            b: bool
            c: Optional[str] = None
        name = Foo.__qualname__
        foo1 = Foo(0, False, None)
        self.assertEqual(repr(foo1), f'{name}(a=0, b=False, c=None)')

    def test_repr_hidden_null(self):
        """ensure repr (hidden on null) works as intended"""
        @dataclass(hide_repr='null')
        class Foo:
            a: Optional[str]
            b: int
            c: List[str]
            d: bool
        name = Foo.__qualname__
        foo1 = Foo(None, 0, [], False)
        self.assertEqual(repr(foo1), f'{name}(b=0, c=[], d=False)')

    def test_repr_empty(self):
        """ensure repr (hidden on empty) works as intended"""
        @dataclass(hide_repr='empty')
        class Foo:
            a: Optional[str]
            b: int
            c: List[str]
            d: bool
        name = Foo.__qualname__
        foo1 = Foo(None, 0, [], False)
        self.assertEqual(repr(foo1), f'{name}(b=0, d=False)')

    def test_initvar(self):
        """ensure InitVar works as intended"""
        @dataclass
        class T:
            a: int
            b: InitVar[int]

            def __post_init__(self, b: int):
                self.extra = b
        t = T(1, 2)
        self.assertEqual(t.a, 1)
        self.assertFalse(hasattr(t, 'b'))
        self.assertTrue(hasattr(t, 'extra'))
        self.assertEqual(t.extra, 2)

    def test_classvar(self):
        """ensure ClassVar works as intended"""
        @dataclass
        class T:
            a: ClassVar[int] = 0
            b: int
        t = T(1)
        self.assertEqual(t.b, 1)
        self.assertNotIn('a', [f.name for f in fields(t)])

    def test_compat(self):
        """validate backwards compatability w/ stdlib dataclasses"""
        @dataclasses.dataclass
        class Foo:
            a: int
            b: dataclasses.InitVar[int]
            c: List[str] = dataclasses.field(default_factory=list, repr=False)
        @dataclass(compat=True)
        class Bar(Foo):
            d: int = 0
            def __post_init__(self, b: int):
                self.extra = b
        bar = Bar(1, 2, d=6)
        self.assertEqual(bar.a, 1)
        self.assertEqual(bar.d, 6)
        self.assertListEqual(bar.c, [])
        self.assertTrue(hasattr(bar, 'extra'))
        self.assertEqual(bar.extra, 2)
        self.assertTrue(is_dataclass(Bar))
        self.assertTrue(dataclasses.is_dataclass(Bar))
        self.assertTrue(len(dataclasses.fields(Bar)) == 3)

    def test_frozen(self):
        """validate frozen attribute works"""
        @dataclass
        class Foo:
            a: int = 0
        @dataclass
        class Bar(Foo):
            b: int = field(default=1, frozen=True)
        bar = Bar(1, 2)
        bar.a = 3
        self.assertRaises(FrozenInstanceError, bar.__setattr__, 'b', 4)

    def test_frozen_inherit(self):
        """ensure frozen inherrit fails when baseclass not frozen"""
        @dataclass
        class Foo:
            a: int = 0
        class Bar(Foo):
            b: int = field(default=1, frozen=True)
        self.assertRaises(TypeError, dataclass, Bar, frozen=True)

    def test_asdict(self):
        """ensure asdict function as intended"""
        @dataclass
        class Foo:
            a: int = 0
        @dataclass
        class Bar:
            foo: Foo
            b:   int       = 1
            c:   List[str] = field(default_factory=list)
        b = Bar(Foo(1), 2)
        self.assertDictEqual(asdict(b), {'foo': {'a': 1}, 'b': 2, 'c': []})

    def test_astuple(self):
        """ensure astuple function as intended"""
        @dataclass
        class Foo:
            a: int = 0
        @dataclass
        class Bar:
            foo: Foo
            b:   int       = 1
            c:   List[str] = field(default_factory=list)
        bar = Bar(Foo(1), 2)
        tup = astuple(bar)
        self.assertIsInstance(tup, tuple)
        self.assertListEqual(list(tup), [(1, ), 2, []])

    def test_slots(self):
        """ensure slots generation works as intended"""
        @dataclass(slots=True)
        class Foo:
            a: int
            b: int
            c: InitVar[int]
        self.assertTrue(hasattr(Foo, '__slots__'))
        self.assertEqual(Foo.__slots__, ('a', 'b', ))

"""
PyDerive Validation Extension UnitTests
"""
from enum import Enum
from typing import Dict, List, Set, Tuple, TypeVar, Union, Generic
from unittest import TestCase

from ...dataclasses import dataclass
from ...extensions.validate import FieldValidationError, BaseModel, validate

#** Variables **#
__all__ = ['ValidationTests', 'ValidationModelTests', 'GenericValidationTests']

#** Classes **#

class ValidationTests(TestCase):
    """Validation Decorator UnitTests"""

    def test_simple(self):
        """ensure simple validations work properly"""
        @validate
        class Foo:
            a: int
            b: str
            c: float
        Foo(1, 'ok', 2.1)
        self.assertRaises(FieldValidationError, Foo, 1.2, 'a', 3.4)
        self.assertRaises(FieldValidationError, Foo, 5, 6, 7)
        self.assertRaises(FieldValidationError, Foo, 9, 'c', 10)

    def test_typecast_simple(self):
        """ensure simple typecasting works"""
        @validate(typecast=True)
        class Foo:
            a: int
            b: str
            c: float
        _ = Foo(1, 'ok', 2.1)
        foo3, foo4 = Foo('1', 7, 1), Foo(1, '7', 1.0) #type: ignore
        foo5, foo6 = Foo(1.1, 2.1, '3.1'), Foo(1, '2.1', 3.1) #type: ignore
        self.assertEqual(foo3, foo4)
        self.assertEqual(foo5, foo6)

    def test_sequence(self):
        """ensure sequence validation works properly"""
        @validate
        class Foo:
            a: List[int]
            b: Set[float]
        Foo([1, 2, 3], {1.1, 2.2, 3.3})
        self.assertRaises(FieldValidationError, Foo, (1, 2, 3), {1.1, 2.2, 3.3})
        self.assertRaises(FieldValidationError, Foo, {1, 2, 3}, {1.1, 2.2, 3.3})
        self.assertRaises(FieldValidationError, Foo, [1, 2, 3], [1.1, 2.2, 3.3])
        self.assertRaises(FieldValidationError, Foo, [1, 2, 3], (1.1, 2.2, 3.3))
        self.assertRaises(FieldValidationError, Foo, [1, 2, '3'], {1.1, 2.2, 3.3})
        self.assertRaises(FieldValidationError, Foo, [1, 2, 3.0], {1.1, 2.2, 3.3})
        self.assertRaises(FieldValidationError, Foo, [1, 2, 3], {1.1, 2.2, 3})
        self.assertRaises(FieldValidationError, Foo, [1, 2, 3], {'1.1', 2.2, 3.3})

    def test_typecast_sequence(self):
        """ensure sequence typecasting works"""
        @validate(typecast=True)
        class Foo:
            a: List[int]
            b: Set[float]
        foo1 = Foo([1, 2, 3], {1.1, 2.2, 3.3}) #type: ignore
        foo2 = Foo({1, 2, 3}, (1.1, 2.2, 3.3)) #type: ignore
        foo3 = Foo((1, 2, 3), [1.1, 2.2, 3.3]) #type: ignore
        foo4 = Foo([1.0, '2', 3], {1.1, 2.2, '3.3'}) #type: ignore
        self.assertEqual(foo1, foo2)
        self.assertEqual(foo1, foo3)
        self.assertEqual(foo1, foo4)

    def test_tuple(self):
        """ensure tuple validation works properly"""
        @validate
        class Foo:
            a: Tuple[int, float, str]
            b: Tuple[int, ...]
        Foo((1, 1.2, 'ok'), (1, 2, 3, 4, 5))
        self.assertRaises(FieldValidationError, Foo, [1, 1.2, 'ok'], (1, ))
        self.assertRaises(FieldValidationError, Foo, (1, 1.2, 'ok'), [1, ])
        self.assertRaises(FieldValidationError, Foo, (1, 1.2, ), (1, ))
        self.assertRaises(FieldValidationError, Foo, (1, 1.2, 'ok', 3), (1, ))
        self.assertRaises(FieldValidationError, Foo, (1.1, 1.2, 'ok'), (1, ))
        self.assertRaises(FieldValidationError, Foo, (1, 2, 'ok'), (1, ))
        self.assertRaises(FieldValidationError, Foo, (1, 1.2, 3), (1, ))
        self.assertRaises(FieldValidationError, Foo, (1, 1.2, 'ok'), (1, 'ok', ))

    def test_typecast_tuple(self):
        """ensure tuple typecasting works properly"""
        @validate(typecast=True)
        class Foo:
            a: Tuple[int, float, str]
            b: Tuple[int, ...]
        foo1 = Foo((1, 1.2, 'ok'), (1, 2, 3, 4, 5))
        foo2 = Foo([1.0, '1.2', 'ok'], [1, 2.0, '3', 4, 5]) #type: ignore
        self.assertEqual(foo1, foo2)
        self.assertRaises(FieldValidationError, Foo, (1, 1.2, ), (1, ))
        self.assertRaises(FieldValidationError, Foo, (1, 1.2, 'ok', 3), (1, ))

    def test_union(self):
        """ensure union validation works properly"""
        @validate
        class Foo:
            a: Union[int, str]
        _ = Foo(1), Foo('ok')
        self.assertRaises(FieldValidationError, Foo, 1.1)
        self.assertRaises(FieldValidationError, Foo, [])
        self.assertRaises(FieldValidationError, Foo, object())

    def test_typecast_union(self):
        """ensure union typecasting works properly"""
        @validate(typecast=True)
        class Foo:
            a: Union[int, str]
        foo1, foo2 = Foo(1), Foo('76')
        foo3, foo4 = Foo(1.1), Foo(76) #type: ignore
        self.assertEqual(foo1, foo3)
        self.assertNotEqual(foo2, foo4)

    def test_enum(self):
        """ensure enum validation works properly"""
        class E(Enum):
            A = 'foo'
            B = 'bar'
        @validate
        class Foo:
            a: E
        _ = Foo(E.A), Foo(E.B)
        self.assertRaises(FieldValidationError, Foo, 'A')
        self.assertRaises(FieldValidationError, Foo, 'B')
        self.assertRaises(FieldValidationError, Foo, 'foo')
        self.assertRaises(FieldValidationError, Foo, 'bar')

    def test_typecast_enum(self):
        """ensure enum typecasting works properly"""
        class E(Enum):
            A = 'foo'
            B = 'bar'
        @validate(typecast=True)
        class Foo:
            a: E
        foo1, foo2 = Foo(E.A), Foo(E.B)
        foo3, foo4 = Foo('A'), Foo('B') #type: ignore
        foo5, foo6 = Foo('foo'), Foo('bar') #type: ignore
        self.assertEqual(foo1, foo3)
        self.assertEqual(foo1, foo5)
        self.assertEqual(foo2, foo4)
        self.assertEqual(foo2, foo6)
        self.assertRaises(FieldValidationError, Foo, 'asdf')

class ValidationModelTests(TestCase):
    """Validator BaseModel UnitTests"""

    def test_model(self):
        """validate `BaseModel` generates validator dataclass"""
        class Foo(BaseModel):
            a: int
            b: str
            c: float
        Foo(1, 'ok', 2.1)
        self.assertRaises(FieldValidationError, Foo, 1.2, 'a', 3.4)
        self.assertRaises(FieldValidationError, Foo, 5, 6, 7)
        self.assertRaises(FieldValidationError, Foo, 9, 'c', 10)

    def test_model_typecast(self):
        """validate `BaseModel` can typecast values"""
        class Foo(BaseModel, typecast=True):
            a: int
            b: str
            c: float
        _ = Foo(1, 'ok', 2.1)
        foo3, foo4 = Foo('1', 7, 1), Foo(1, '7', 1.0) #type: ignore
        foo5, foo6 = Foo(1.1, 2.1, '3.1'), Foo(1, '2.1', 3.1) #type: ignore
        self.assertEqual(foo3, foo4)
        self.assertEqual(foo5, foo6)

    def test_model_validate(self):
        """ensure `BaseModel.validate` function works as intended"""
        class Foo(BaseModel):
            a: List[str]
        foo = Foo(['a', 'b', 'c'])
        foo.validate()
        foo.a.extend(['d', 1]) #type: ignore
        self.assertRaises(FieldValidationError, foo.validate)

    def test_model_parsing(self):
        """ensure `BaseModel.parse_obj` function works as intended"""
        class Bar(BaseModel):
            x: Union[float, str]
        class Foo(BaseModel):
            a:   Tuple[int, str, float]
            bar: Bar
        foo1 = Foo.parse_obj({'a': (1, 'ok', 2.1), 'bar': {'x': 1.1}})
        foo2 = Foo.parse_obj(((1, 'ok', 2.1), [1.1]))
        self.assertEqual(foo1, foo2)
        self.assertRaises(FieldValidationError, Foo.parse_obj, {'a': (1.0, 'ok', 2.1), 'bar': {'x': 'ok'}})

    def test_model_complex(self):
        """ensure `BaseModel`.valdiate function works on complex objects"""
        class Bar(BaseModel):
            i: Tuple[str, int, float]
        class Foo(BaseModel):
            d: Dict[str, Bar]
            l: List[Union[int, Bar]]
            t: Tuple[bool, Bar, int]
        foo1 = {'d': {'k1': {'i': ('a', 1, 1.1)}}, 'l': [7, 8], 't': (True, {'i': ('b', 2, 2.2)}, 3)}
        foo2 = {'d': {'k1': {'i': ('a', 1, 1.1)}}, 'l': [7, 8], 't': (True, {'i': ('b', 2, 2.2)}, 3.1)}
        foo3 = {'d': {'k1': {'i': ('a', 1, 1.1)}}, 'l': [7, 8.8], 't': (True, {'i': ('b', 2, 2.2)}, 3)}
        foo4 = {'d': {'k1': {'i': ('a', 1, 1.1)}}, 'l': [7, 8], 't': (True, {'i': ('b', 2, 2)}, 3)}
        foo5 = {'d': {'k1': {'i': ('a', 1, 1.1)}}, 'l': [7, 8], 't': (True, {'i': ('b', 2.2)}, 3)}
        Foo.parse_obj(foo1)
        self.assertRaises(FieldValidationError, Foo.parse_obj, foo2)
        self.assertRaises(FieldValidationError, Foo.parse_obj, foo3)
        self.assertRaises(FieldValidationError, Foo.parse_obj, foo4)
        self.assertRaises(FieldValidationError, Foo.parse_obj, foo5)

    def test_model_subclass(self):
        """test `BaseModel` inherritance of another dataclass"""
        @dataclass
        class Bar:
            x: int
        class Foo(Bar, BaseModel):
            a: str
        foo = Foo(1, 'a')
        self.assertEqual(foo.x, 1)
        self.assertEqual(foo.a, 'a')
        self.assertRaises(FieldValidationError, Foo, '1', 'a')
        self.assertRaises(FieldValidationError, Foo, 1, 2)

class GenericValidationTests(TestCase):
    """Validation for Generics UnitTests"""

    def test_simple(self):
        """test simple generics assignemnt"""
        T = TypeVar('T')
        class Foo(BaseModel, Generic[T]):
            value: T
        class Bar(Foo[int]):
            pass
        class Baz(Foo[int], typecast=True):
            pass
        self.assertEqual(Foo(1).value, 1)
        self.assertEqual(Foo('a').value, 'a')
        self.assertEqual(Foo(1.0).value, 1.0)
        self.assertEqual(Foo([]).value, [])
        self.assertRaises(FieldValidationError, Bar, '1')
        self.assertRaises(FieldValidationError, Bar, 1.0)
        self.assertEqual(Baz(1).value, 1)
        self.assertEqual(Baz('1').value, 1) #type: ignore
        self.assertEqual(Baz(1.0).value, 1) #type: ignore

    def test_typevars(self):
        """test more complex typevars with generics"""
        T = TypeVar('T', bound=Union[int, float, bool])
        class Foo(BaseModel, Generic[T]):
            a: T
            b: List[T]
            c: Tuple[str, T]
        class Bar(Foo[int]):
            pass
        foo = Foo(1, [2, 3.0], ('a', False))
        _   = Bar(1, [2, 3], ('a', 4))
        self.assertEqual(foo.a, 1)
        self.assertListEqual(foo.b, [2, 3.0])
        self.assertTupleEqual(foo.c, ('a', False))
        self.assertRaises(FieldValidationError, Foo, 1, [2], ('a', 'b'))
        self.assertRaises(FieldValidationError, Foo, 1, ['a'], ('b', 2))
        self.assertRaises(FieldValidationError, Foo, 'a', [2], ('b', 3.0))
        self.assertRaises(FieldValidationError, Bar, 1, [2], ('a', 3.0))
        self.assertRaises(FieldValidationError, Bar, 1, [2.0], ('a', 3))
        self.assertRaises(FieldValidationError, Bar, 1.0, [2], ('a', 3))

    def test_complex(self):
        """test complex generic setup w/ heigharchy of validators"""
        T = TypeVar('T', bound=Union[int, float, bool])
        class Foo(BaseModel, Generic[T]):
            x: T
        class Bar(BaseModel, Generic[T]):
            a:   T
            foo: Foo[T]
        class Baz(Bar[int]):
            pass
        bar = Bar(1, Foo(2.0))
        self.assertEqual(bar.a, 1)
        self.assertEqual(bar.foo.x, 2.0)
        self.assertRaises(FieldValidationError, Baz, 'a', Foo(1))
        self.assertRaises(FieldValidationError, Baz, 1, Foo(2.0))

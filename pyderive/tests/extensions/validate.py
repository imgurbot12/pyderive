"""
PyDerive Validation Extension UnitTests
"""
from enum import Enum
from typing import List, Set, Tuple, Union
from unittest import TestCase

from ...extensions.validate import ValidationError, BaseModel, validate

#** Variables **#
__all__ = ['ValidationTests']

#** Classes **#

class ValidationTests(TestCase):

    def test_simple(self):
        """ensure simple validations work properly"""
        @validate
        class Foo:
            a: int
            b: str
            c: float
        Foo(1, 'ok', 2.1)
        self.assertRaises(ValidationError, Foo, 1.2, 'a', 3.4)
        self.assertRaises(ValidationError, Foo, 5, 6, 7)
        self.assertRaises(ValidationError, Foo, 9, 'c', 10)

    def test_sequence(self):
        """ensure sequence validation works properly"""
        @validate
        class Foo:
            a: List[int]
            b: Set[float]
        Foo([1, 2, 3], {1.1, 2.2, 3.3})
        self.assertRaises(ValidationError, Foo, (1, 2, 3), {1.1, 2.2, 3.3})
        self.assertRaises(ValidationError, Foo, {1, 2, 3}, {1.1, 2.2, 3.3})
        self.assertRaises(ValidationError, Foo, [1, 2, 3], [1.1, 2.2, 3.3])
        self.assertRaises(ValidationError, Foo, [1, 2, 3], (1.1, 2.2, 3.3))
        self.assertRaises(ValidationError, Foo, [1, 2, '3'], {1.1, 2.2, 3.3})
        self.assertRaises(ValidationError, Foo, [1, 2, 3.0], {1.1, 2.2, 3.3})
        self.assertRaises(ValidationError, Foo, [1, 2, 3], {1.1, 2.2, 3})
        self.assertRaises(ValidationError, Foo, [1, 2, 3], {'1.1', 2.2, 3.3})

    def test_tuple(self):
        """ensure tuple validation works properly"""
        @validate
        class Foo:
            a: Tuple[int, float, str]
            b: Tuple[int, ...]
        Foo((1, 1.2, 'ok'), (1, 2, 3, 4, 5))
        self.assertRaises(ValidationError, Foo, [1, 1.2, 'ok'], (1, ))
        self.assertRaises(ValidationError, Foo, (1, 1.2, 'ok'), [1, ])
        self.assertRaises(ValidationError, Foo, (1, 1.2, ), (1, ))
        self.assertRaises(ValidationError, Foo, (1, 1.2, 'ok', 3), (1, ))
        self.assertRaises(ValidationError, Foo, (1.1, 1.2, 'ok'), (1, ))
        self.assertRaises(ValidationError, Foo, (1, 2, 'ok'), (1, ))
        self.assertRaises(ValidationError, Foo, (1, 1.2, 3), (1, ))
        self.assertRaises(ValidationError, Foo, (1, 1.2, 'ok'), (1, 'ok', ))

    def test_union(self):
        """ensure union validation works properly"""
        @validate
        class Foo:
            a: Union[int, str]
        _ = Foo(1), Foo('ok')
        self.assertRaises(ValidationError, Foo, 1.1)
        self.assertRaises(ValidationError, Foo, [])
        self.assertRaises(ValidationError, Foo, object())

    def test_enum_value(self):
        """ensure enum validation works properly"""
        class Bar1(Enum):
            A = 'foo'
            B = 'bar'
        # @validate(typecast=True)
        # class Foo:
        #     a: Test
        # foo1, foo2 = Foo(Test.A), Foo(Test.B)
        # foo3, foo4 = Foo('A'), Foo('B')
        # foo5, foo6 = Foo('foo'), Foo('bar')
        # self.assertListEqual([foo1, foo2], [foo3, foo4])
        # self.assertListEqual([foo1, foo2], [foo5, foo6])
        # self.assertRaises(ValidationError, Foo, 'A')
        # self.assertRaises(ValidationError, Foo, 'B')
        # self.assertRaises(ValidationError, Foo, 'foo')
        # self.assertRaises(ValidationError, Foo, 'bar')

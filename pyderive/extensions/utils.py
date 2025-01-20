"""
Shared Utilities Between Extensions
"""
import sys
import typing
from typing import ForwardRef, Type

#** Variables **#
__all__ = ['deref']

#** Functions **#

def deref(base: object, ref: ForwardRef) -> Type:
    """
    dereference ForwardRef annotation

    :param base: associated reference object (dataclass)
    :param ref:  forward-reference annotation
    :return:     dereferenced type
    """
    module   = getattr(base, '__module__')
    nglobals = getattr(sys.modules.get(module, None), '__dict__', {})
    nlocals  = dict(vars(base))
    return typing._eval_type(ref, nglobals, nlocals) #type: ignore

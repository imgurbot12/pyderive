"""
Generic Dataclass Helpers
"""
import types
import typing
import functools
from copy import deepcopy
from typing import TypeVar, List, Tuple, Type, Generic, Union, Any
from typing_extensions import get_origin, get_args, cast

from .validators import is_autogen
from ...dataclasses import FIELD_ATTR, dataclass

#** Variables **#
__all__ = [
    'BASE_VAR',
    'BASES_ATTR',
    'GENERIC_PARAMS',

    'has_generics',
    'is_generic_instance',
    'find_generics',
    'update_generics',
    'generic_getitem'
]

#: generic for generic_getitem
T = TypeVar('T', bound=Type)

#: variable to store generic baseclass if not already stored
BASE_VAR = '__generic_base__'

#: typing internal tracker for origin bases
BASES_ATTR = '__orig_bases__'

#: typing internal tracker for generic parameters
GENERIC_PARAMS = '__parameters__'

#** Enums **#

@dataclass(slots=True)
class TypeVariable:
    var: TypeVar

@dataclass(slots=True)
class TypeAssign:
    vars: List[TypeVar]

#: rust-like enum of generic type assignments
GenericType = Union[TypeVariable, TypeAssign]

#** Functions **#

def has_generics(cls: Type) -> bool:
    """
    check if dataclass object has generics

    :return: true if generics exist else false
    """
    return hasattr(cls, BASES_ATTR)

def is_generic_instance(item: Any, inst: Type) -> bool:
    """
    confirm if item is baseclass generic of inst

    :param item: item to compare to instance
    :param inst: type instance to compare to item object
    :return:     true if item is an instance of the inst varaible
    """
    return getattr(inst, BASE_VAR, None) == type(item)

def find_generics(cls: Type) -> Union[TypeVar, List[TypeVar], None]:
    """
    recursively check if annotation has generic within

    :return: true if type contains any generics
    """
    if isinstance(cls, TypeVar):
        return cls
    # get typevars from GenericAlias
    if isinstance(cls, typing._GenericAlias): #type: ignore
        params = getattr(cls, GENERIC_PARAMS, ())
        return list(params) if params else None
    # get typevars from generic class
    if has_generics(cls):
        bases = getattr(cls, BASES_ATTR, ())
        if bases:
            return find_generics(bases[0])
    # get typevars from arguments
    generics = []
    for arg in get_args(cls):
        generic = find_generics(arg)
        if generic is not None:
            if isinstance(generic, list):
                generics.extend(generic)
            else:
                generics.append(generic)
    if generics:
        return generics

def update_generics(cls: Type):
    """
    Update field annotations associated w/ dataclass based on Generics

    :param cls: dataclass object that contains generics
    """
    # get fields and confirm dataclass
    fields = getattr(cls, FIELD_ATTR, None)
    if fields is None:
        raise ValueError(f'{cls.__name__} is not a dataclass')
    # retrieve associated fields w/ generics and find contained typevars
    generics = []
    for pos, field in enumerate(fields, 0):
        fgenerics = find_generics(field.anno)
        if fgenerics:
            generics.append((pos, field, fgenerics))
    if not generics:
        return
    # retrieve args associated w/ baseclass generics
    bases: List[Tuple[int, Type]]
    bases   = [(0, b) for b in getattr(cls, BASES_ATTR, ())]
    arglist = []
    while bases:
        depth, base = bases.pop(0)
        origin      = get_origin(base)
        if origin is None:
            continue
        depth += 1
        sbases = getattr(origin, BASES_ATTR, ())
        bases.extend([(depth, sb) for sb in sbases])
        arglist.append((depth, list(get_args(base))))
    # skip if no generic typevars were found
    if not arglist:
        return
    arglist.sort(key=lambda x: x[0], reverse=True)
    # generate mapping of generics to their assigned values
    final      = []
    typevars   = {}
    last_depth = 0
    for depth, args in arglist:
        if depth == last_depth:
            continue
        # update final argument values
        if len(args) < len(final):
            # fill in positions if args are less than final
            for n, arg in enumerate(final, 0):
                if isinstance(arg, TypeVar):
                    final[n] = args.pop(0)
                    if not args:
                        break
        else:
            final = args
        # update typevars
        for n, arg in enumerate(args, 0):
            if isinstance(arg, TypeVar):
                typevars[n] = arg
        # update previous trackers
        last_depth = last_depth
    # generate final typevar -> assignment map
    typemap = {v:final[pos] for pos,v in typevars.items()}
    fields  = fields.copy()
    for pos, field, fgenerics in generics:
        # copy field and update annotations
        field = deepcopy(field)
        if isinstance(fgenerics, list):
            typevars   = [typemap.get(anno, anno) for anno in fgenerics]
            typevars   = typevars[0] if len(typevars) == 1 else tuple(typevars)
            field.anno = field.anno[typevars]
        else:
            field.anno  = typemap.get(field.anno, field.anno)
        # reset validator for reassignment if autogenerated
        if field.validator and is_autogen(field.validator):
            field.validator = None
        fields[pos] = field
    setattr(cls, FIELD_ATTR, fields)

#NOTE: Hacky AF. Retrieves underlying base Generic getitem
# function to generate and alias, generates a subclass from
# alias as would be typical and then updates the associated
# fields w/ new type assignments
@classmethod
@functools.lru_cache(maxsize=None)
def generic_getitem(cls: T, args: Tuple[Type, ...]) -> T:
    """
    custom getitem to build subclass
    """
    from . import validate
    # skip generation if args match builtins
    params  = list(args) if isinstance(args, tuple) else [args]
    builtin = find_generics(cls)
    if builtin == params:
        return cls
    # generate new class from generic-alias
    func   = Generic.__class_getitem__.__wrapped__ #type: ignore
    alias  = func(cls=cls, params=args)
    newcls = types.new_class(str(alias).split('.', 1)[-1], (alias, ))
    # update field annotations based on generics and update validators
    update_generics(newcls)
    validate(newcls)
    # track generic baseclass if not already tracked
    if not hasattr(newcls, BASE_VAR):
        setattr(newcls, BASE_VAR, cls)
    return cast(T, newcls)

"""
DataClass Compiler Utilities
"""
from reprlib import recursive_repr
from types import FunctionType
from typing import Type, List, Optional, Any, Callable, Dict

from .abc import *

#** Variables **#
__all__ = [
    'POST_INIT',
    'HDF',
    'HDF_VAR',

    'create_init',
    'create_repr',
    'create_compare',
    'create_hash',
    'assign_func',
    'add_slots',
    'freeze_fields',
]

#: post init function
POST_INIT = '__post_init__'

#: custom type to declare variable has a default factory
HDF = type('HAS_DEFAULT_FACTORY', (), {})

#: variable used to reference custom has-default-factory type
HDF_VAR = f'_{HDF.__name__}'

#** Functions **#

def _create_fn(
    name:        str, 
    args:        List[str], 
    body:        List[str], 
    locals:      Optional[dict] = None,
    globals:     Optional[dict] = None,
    return_type: Any            = MISSING
):
    """create python function from specifications"""
    locals  = locals or {}
    globals = globals or {}
    # build code as string
    return_anno = ''
    if return_type is not MISSING:
        locals['_return_type'] = return_type
        return_anno = '->_return_type'
    sargs = ','.join(args)
    sbody = '\n'.join(f' {b}' for b in body)
    func  = f'def {name}({sargs}){return_anno}:\n{sbody}'
    # compute function text as python object
    exec(func, globals, locals)
    return locals[name]

def _init_param(field: FieldDef) -> str:
    """generate field argument parameter"""
    if field.default is MISSING and field.default_factory is MISSING:
        default = ''
    elif field.default is not MISSING:
        default = f'=_init_{field.name}'
    else:
        default = f'={HDF_VAR}'
    return f'{field.name}{default}'

def _init_value(field: FieldDef, globals: dict) -> str:
    """generate init field-value assignment"""
    init_name = f'_init_{field.name}'
    if field.default_factory is not MISSING:
        if field.init:
            globals[init_name] = field.default_factory
            return f'{init_name}() if {field.name}' + \
                f' is {HDF_VAR} else {field.name}'
        else:
            globals[init_name] = field.default_factory
            return f'{init_name}()'
    # no default factory
    if field.init:
        if field.default is not MISSING:
            globals[init_name] = field.default
        return field.name
    # not default factory - is not init
    if field.default is not MISSING:
        globals[init_name] = field.default
        return init_name
    raise TypeError(f'field {field.name!r} has no default value')

def _init_assign(self_name: str, name: str, value: str, frozen: bool) -> str:
    """generate field variable assignment"""
    if frozen:
        return f'object.__setattr__({self_name}, {name!r}, {value})'
    return f'{self_name}.{name}={value}'

def create_init(
    fields:    Fields,
    kw_only:   bool = False, 
    post_init: bool = False,
    frozen:    bool = False,
) -> Callable:
    """
    generate dynamic init-function from the following args/kwargs

    :param fields:    ordered field used to generate init-args/func-body
    :param kw_only:   override kw-only to make everything kw-only 
    :param post_init: enable post-init when true
    :return:          generated init-function made from specifications
    """
    self_name = 'self'
    locals:  Dict[str, Any] = {}
    globals: Dict[str, Any] = {HDF_VAR: HDF}
    args, post, body, kwonly = ['self'], [], [], []
    for field in fields:
        # build parameter code
        name  = field.name
        param = _init_param(field)
        if field.field_type == FieldType.INIT_VAR:
            if field.default_factory is not MISSING:
                raise TypeError(
                    f'init field {name!r} cannot have a default factory')
            post.append(name)
        if field.init:
            if kw_only or field.kw_only:
                kwonly.append(param)
            else:
                args.append(param)
        # build body code
        value  = _init_value(field, globals)
        assign = _init_assign(self_name, name, value, frozen or field.frozen)
        body.append(assign)
    # ensure body exists
    if post_init or post:
        params = ', '.join(post)
        body.append(f'self.{POST_INIT}({params})')
    if not body:
        body.append('pass')
    # generate function args/kwargs
    if kwonly:
        args.append('*')
        args.extend(kwonly)
    return _create_fn('__init__', args, body, locals, globals)

def create_repr(fields: Fields) -> Callable:
    """
    generate simple repr-function for the following field-structure

    :param fields: ordered field used to generate repr-func
    :param return: repr-function
    """
    names = [f.name for f in fields if f.repr] 
    body  = 'return self.__class__.__qualname__ + f"(' + \
        ', '.join(f'{name}={{self.{name}!r}}' for name in names) + ')"'
    func = _create_fn('__repr__', ['self'], [body])
    return recursive_repr('...')(func)

def _tuple_str(params: List[str], prefix: Optional[str] = None) -> str:
    """generate tuple string for the given params"""
    if not params:
        return '()'
    items = (f'{prefix}.{param}' for param in params) if prefix else params
    return '(' + ', '.join(items) + ',)'

def create_compare(fields: Fields, func: str, op: str) -> Callable:
    """
    generate compare function w/ the following function name/operation

    :param fields: ordered fields used to generate compare-func
    :param func:   function name string
    :param op:     function compare operation
    :return:       compare-function
    """
    names  = [f.name for f in fields if f.compare]
    self_t  = _tuple_str(names, 'self') 
    other_t = _tuple_str(names, 'other')  
    return _create_fn(func, ['self', 'other'], [
         'if other.__class__ is self.__class__:',
        f' return {self_t} {op} {other_t}',
         'raise NotImplemented',
    ])

def create_hash(fields: Fields) -> Callable:
    """
    generate hash-function for hashable fields

    :param fields: ordered fields used to generate hash-function
    :return:       hash-function
    """
    names   = [f.name for f in fields if f.hash]
    names_t = _tuple_str(names, 'self')
    return _create_fn('__hash__', ['self'], [f'return hash({names_t})'])

def assign_func(cls: Type, func: Callable, 
    name: Optional[str] = None, overwrite: bool = False) -> bool:
    """
    assign function to the object and modify qualname

    :param cls:       class object to assign to
    :param func:      function to assign to value
    :param name:      name of function to assign
    :param overwrite: allow for overwrite if enabled
    :return:          true if object already exists else false
    """
    name = name or func.__name__
    if not overwrite and name in cls.__dict__:
        return True
    if isinstance(func, FunctionType):
        func.__qualname__ = f'{cls.__qualname__}.{func.__name__}'
    setattr(cls, name, func)
    return False

def add_slots(cls: Type, fields: Fields, frozen: bool = False) -> Type:
    """
    generate slots for fields connected to the given class object

    :param cls:    class-object to assign slots onto
    :param struct: field structure to control slot definition
    :return:       updated class object
    """
    cls_dict = dict(cls.__dict__)
    if '__slots__' in cls_dict:
        raise TypeError(f'{cls.__name__} already specifies __slots__')
    # ensure slots don't overlap with bases-classes and assign to dict
    slots      = [f.name for f in fields]
    bases      = cls.__mro__[1:-1]
    base_slots = {s for b in bases for s in getattr(b, '__slots__', [])}
    cls_dict['__slots__'] = tuple([s for s in slots if s not in base_slots])
    # remove elements from dict before creation
    cls_dict.pop('__dict__', None)
    cls_dict.pop('__weakref__', None)
    for name in slots:
        cls_dict.pop(name, None)
    # recreate class object w/ slots
    qname = getattr(cls, '__qualname__', None)
    cls   = type(cls)(cls.__name__, cls.__bases__, cls_dict) #type: ignore
    if qname is not None:
        cls.__qualname__ = qname
    # implement custom state functions when frozen to enable proper pickling
    if frozen or any(f.frozen for f in fields):
        names_t  = _tuple_str([repr(name) for name in slots]) 
        values_t = _tuple_str(slots, 'self')
        getstate = _create_fn('__getstate__', ['self'], [f'return {values_t}'])
        setstate = _create_fn('__setstate__', ['self', 'state'], [
            f'for name, value in zip({names_t}, state):',
            f' object.__setattr__(self, name, value)'
        ])
        assign_func(cls, getstate)
        assign_func(cls, setstate)
    return cls

def freeze_fields(cls: Type, struct: FlatStruct, frozen: bool = False):
    """
    add custom __setattr__/__delattr__ funcs to prevent field modification

    :param cls:    class object to assign functions to
    :param struct: field structure to control frozen status
    :param frozen: override field frozen status
    """
    fields = []
    for name in struct.order:
        field = struct.fields[name]
        if frozen or field.frozen:
            fields.append(repr(name))
    names   = _tuple_str(fields)
    globals = {'cls': cls, 'FrozenInstanceError': FrozenInstanceError}
    ifstmt  = f'if name in {names}:'
    setattr = _create_fn('__setattr__', ['self', 'name', 'value'], [
        ifstmt,
        ' raise FrozenInstanceError(f"cannot assign to field {name!r}")',
        'super(cls, self).__setattr__(name, value)'
    ], globals=globals)
    delattr = _create_fn('__delattr__', ['self', 'name'], [
        ifstmt,
        ' raise FrozenInstanceError(f"cannot delete field {name!r}")',
        'super(cls, self).__delattr__(name)'
    ], globals=globals)
    assign_func(cls, setattr)
    assign_func(cls, delattr)

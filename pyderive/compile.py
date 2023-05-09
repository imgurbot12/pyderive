"""
DataClass Compiler Utilities
"""
from typing import List, Optional, Any, Dict

from .abc import MISSING, FlatStruct

#** Variables **#

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
    locals = locals or {}
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

def create_init(
    fields: FlatStruct, kw_only: bool = False, post_init: bool = True):
    """
    generate dynamic init-function from the following args/kwargs
    """
    items = [(name, fields.fields[name].value) for name in fields.order]
    args  = [k for k,v in items if v is MISSING]
    args += [f'{k}={v!r}' for k,v in items if v is not MISSING]
    body  = [f'self.{k}={k}' for k,_ in items]
    print(args, body)

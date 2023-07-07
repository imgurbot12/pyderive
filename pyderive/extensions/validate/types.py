"""
Custom Annotated Validator Types
"""
from datetime import datetime, timedelta
import os
import re
import logging
from ipaddress import *
from typing import Union
from typing_extensions import Annotated
from urllib.parse import urlsplit

from .validators import *

#** Variables **#
__all__ = [
    'IPv4',
    'IPv6',
    'IPvAnyAddress',
    'IPvAnyNetwork',
    'IPvAnyInterface',

    'URL',
    'Domain',
    'Host',
    'Port',
    'ExistingFile',
    'Loglevel',
    'Datetime',
    'Timedelta',
]

_re_domain = re.compile(r'^(?:[a-zA-Z0-9_](?:[a-zA-Z0-9-_]{0,61}' + \
  r'[A-Za-z0-9])?\.)+[A-Za-z0-9][A-Za-z0-9-_]{0,61}[A-Za-z]\.?$')

_re_timedelta = re.compile(r'^(\d+[a-z]+)+$')
_re_timedelta_group = re.compile(r'\d+[a-z]+')

IPv4 = Annotated[Union[IPv4Address, str, bytes], PreValidator[IPv4Address]]
IPv6 = Annotated[Union[IPv6Address, str, bytes], PreValidator[IPv6Address]]

IPvAnyAddress = Annotated[Union[IPv4Address, IPv6Address, str, bytes], PreValidator[ip_address]]
IPvAnyNetwork = Annotated[Union[IPv4Network, IPv6Network, str, bytes], PreValidator[ip_network]]
IPvAnyInterface = Annotated[Union[IPv4Interface, IPv6Interface, str, bytes], PreValidator[ip_interface]]

#** Function **#

def is_url(value: str) -> str:
    """check that value is valid url (very naive approach)"""
    url = urlsplit(value)
    if not url.scheme or not url.netloc:
        raise ValidationError(f'Invalid URL: {value!r}')
    return value

def is_domain(value: str) -> str:
    """check that value is valid domain"""
    if _re_domain.match(value) is None:
        raise ValidationError(f'Invalid Domain: {value!r}')
    return value

def is_existing_file(value: str):
    """check that the specified file exists"""
    if not os.path.exists(value):
        raise ValidationError(f'No such file: {value!r}')
    return value

def is_port(value: int):
    """check that specified value is a port"""
    if value < 0 or value >= (2**16):
        raise ValidationError(f'Invalid Port: {value!r}')
    return value

def is_loglevel(value: 'Loglevel') -> int:
    """check if value is valid loglevel"""
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise ValueError(value)
    try:
        level = getattr(logging, value.upper())
    except AttributeError:
        raise ValueError(value) from None
    if not isinstance(level, int):
        raise ValueError(value)
    return level

def is_datetime(value: 'Datetime') -> datetime:
    """check if value is valid datetime"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value))
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise ValueError(value)

def is_timedelta(value: 'Timedelta') -> timedelta:
    """check if value is a valid timedelta"""
    if isinstance(value, timedelta):
        return value
    if isinstance(value, int):
        return timedelta(seconds=value)
    if not isinstance(value, str):
        raise ValueError(value)
    # attempt to complete regex match
    value = value.strip() 
    if _re_timedelta.match(value) is None:
        raise ValueError(value)
    # separate digit from field name and match to existing fields
    fields = ('weeks', 'days', 'hours', 'minutes', 'seconds')
    kwargs = {}
    for group in _re_timedelta_group.findall(value):
        count = ''.join(c for c in group if c.isdigit())
        field = group[len(count):]
        for possible in fields:
            if possible.startswith(field):
                field = possible
                break
        if field not in fields:
            raise ValueError(f'Invalid Timegroup: {field!r}')
        kwargs[field] = int(count)
    return timedelta(**kwargs)

#** Init **#

#: validate string is a url
URL = Annotated[str, Validator[is_url]]

#: validate string is a domain
Domain = Annotated[str, Validator[is_domain]]

#: validate hostname
Host = Union[IPvAnyAddress, Domain]

#: validate port
Port = Annotated[int, Validator[is_port]]

#: only allow valid and existing filepaths
ExistingFile = Annotated[str, Validator[is_existing_file]]

#: stdlib logging loglevel validator
Loglevel = Annotated[Union[int, str], Validator[is_loglevel]]

#: datetime validator
Datetime = Annotated[Union[str, int, datetime], Validator[is_datetime]]

#: timedelta validator
Timedelta = Annotated[Union[str, int, timedelta], Validator[is_timedelta]]

# register additional validators for common python types
register_validator(datetime, is_datetime)
register_validator(timedelta, is_timedelta)

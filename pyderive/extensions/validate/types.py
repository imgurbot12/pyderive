"""
Custom Annotated Validator Types
"""
from datetime import datetime, timedelta
import os
import re
import logging
from ipaddress import (
    IPv4Address, IPv4Interface, IPv4Network, IPv6Address, IPv6Interface,
    IPv6Network, ip_address, ip_interface, ip_network)
from typing import Any, IO, BinaryIO, TextIO, Union
from typing_extensions import Annotated
from urllib.parse import urlsplit

from .helpers import Regex
from .validators import *

#** Variables **#
__all__ = [
    'IPv4',
    'IPv6',
    'IPvAnyAddress',
    'IPvAnyNetwork',
    'IPvAnyInterface',
    'Domain',
    'Email',
    'UUID',
    'MacAddr',
    'PhoneNumber',

    'Bytes',
    'HexBytes',
    'URL',
    'Host',
    'Port',
    'ExistingFile',
    'Loglevel',
    'Datetime',
    'Timedelta',
]

#: functions needed for IO impl
IO_FUNCS = [var for var, value in vars(IO).items() if callable(value)]

_re_domain = r'^(?:[a-zA-Z0-9_](?:[a-zA-Z0-9-_]{0,61}' + \
  r'[A-Za-z0-9])?\.)+[A-Za-z0-9][A-Za-z0-9-_]{0,61}[A-Za-z]\.?$'

_re_timedelta = re.compile(r'^(\d+[a-z]+)+$')
_re_timedelta_group = re.compile(r'\d+[a-z]+')

_re_email    = r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"""
_re_uuid     = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$'
_re_mac_addr = r'^(?:[a-fA-F0-9]{2}[-:]?){5}[a-fA-F0-9]{2}$'
_re_phone    = r'^(?:\+?\d{1,4}-?)?[0-9]{3}-?[0-9]{3}-?[0-9]{4}$'

IPv4 = Annotated[Union[IPv4Address, str, bytes], PreValidator[IPv4Address]]
IPv6 = Annotated[Union[IPv6Address, str, bytes], PreValidator[IPv6Address]]

IPvAnyAddress = Annotated[Union[IPv4Address, IPv6Address, str, bytes], PreValidator[ip_address]]
IPvAnyNetwork = Annotated[Union[IPv4Network, IPv6Network, str, bytes], PreValidator[ip_network]]
IPvAnyInterface = Annotated[Union[IPv4Interface, IPv6Interface, str, bytes], PreValidator[ip_interface]]

Domain      = Annotated[str, Regex(_re_domain)]
Email       = Annotated[str, Regex(_re_email)]
UUID        = Annotated[str, Regex(_re_uuid)]
MacAddr     = Annotated[str, Regex(_re_mac_addr)]
PhoneNumber = Annotated[str, Regex(_re_phone)]

#** Function **#

def is_bytes(value: Union[str, bytes]) -> bytes:
    """check that the given value is bytes and convert string"""
    if isinstance(value, str):
        return value.encode()
    return value

def is_hexbytes(value: Union[str, bytes]) -> bytes:
    """check that value is bytes and convert hexstrings"""
    if isinstance(value, str):
        return bytes.fromhex(value)
    return value

def is_url(value: str) -> str:
    """check that value is valid url (very naive approach)"""
    url = urlsplit(value)
    if not url.scheme or not url.netloc:
        raise ValueError(f'Invalid URL: {value!r}')
    return value

def is_existing_file(value: str) -> str:
    """check that the specified file exists"""
    if not os.path.exists(value):
        raise ValueError(f'No such file: {value!r}')
    return value

def is_port(value: int) -> int:
    """check that specified value is a port"""
    if value < 0 or value >= (2**16):
        raise ValueError(f'Invalid Port: {value!r}')
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

def is_io(value: Any) -> Any:
    """check if value is valid io object"""
    if all(callable(getattr(value, f, None)) for f in IO_FUNCS):
        return value
    raise ValueError(f'Not Valid IO: {value!r}')

def is_textio(value: Any) -> Any:
    """check if value is textio"""
    if hasattr(value, 'encoding'):
        return is_io(value)
    raise ValueError(f'Not TextIO: {value!r}')

def is_binaryio(value: Any) -> Any:
    """check if value is bytesio"""
    if not hasattr(value, 'encoding'):
        return is_io(value)
    raise ValueError(f'Not BinaryIO: {value!r}')

#** Classes **#

#** Init **#

#: convert string directly into bytes using default encoding
Bytes = Annotated[Union[str, bytes], PreValidator[is_bytes]]

#: convert hexidecimal strings into bytes
HexBytes = Annotated[Union[str, bytes], PreValidator[is_hexbytes]]

#: validate string is a url
URL = Annotated[str, Validator[is_url]]

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
register_validator(bytes, is_bytes)
register_validator(datetime, is_datetime)
register_validator(timedelta, is_timedelta)
register_validator(IO, is_io)
register_validator(TextIO, is_textio)
register_validator(BinaryIO, is_binaryio)

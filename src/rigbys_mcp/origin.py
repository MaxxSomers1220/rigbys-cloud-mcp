"""Explicit public HTTPS origin; no trust in client-supplied proxy headers."""
from ipaddress import IPv6Address
import os
import re
from urllib.parse import urlsplit


_LABEL = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?')
_ERROR = ('RIGBYS_PUBLIC_ORIGIN must be an HTTPS origin without credentials, '
          'a path, a query or a fragment')


def configured_public_origin():
    value = os.environ.get('RIGBYS_PUBLIC_ORIGIN')
    if value is None:
        return None
    try:
        parsed = urlsplit(value)
        hostname, port = parsed.hostname, parsed.port
        if (not value or any(character.isspace() or ord(character) < 32 or ord(character) == 127
                             for character in value)
                or any(character in value for character in ('\\', '?', '#'))
                or parsed.scheme != 'https' or not hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in ('', '/')):
            raise ValueError
        if ':' in hostname:
            authority = '[' + IPv6Address(hostname).compressed + ']'
        else:
            hostname = hostname.encode('idna').decode('ascii').lower()
            if not all(_LABEL.fullmatch(label) for label in hostname.rstrip('.').split('.')):
                raise ValueError
            authority = hostname
        if port is not None and port != 443:
            authority += ':' + str(port)
        return 'https://' + authority
    except (ValueError, UnicodeError):
        # Configuration may accidentally include credentials. Never echo it.
        raise RuntimeError(_ERROR) from None

"""Only fetch image URLs from the configured services, including every redirect."""
import re
from urllib.parse import urljoin, urlsplit

import requests
try:
    from config import Config
except ModuleNotFoundError:
    from config_example import Config


MAX_IMAGE_BYTES = 25 * 1024 * 1024


class ImageLoginRequired(RuntimeError):
    pass


def origin(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('Invalid image URL')
    return parts.scheme, parts.hostname.lower(), parts.port or (443 if parts.scheme == 'https' else 80)


def normalize_tpdb_page(value, section='posters'):
    if not isinstance(value, (str, type(None))):
        raise ValueError('Invalid saved TPDb page')
    value = (value or '').strip()
    if not value:
        return ''
    if value.isdigit():
        return f'{Config.TPDB_BASE_URL}/{section}/{value}'
    parts = urlsplit(value)
    if origin(value) != origin(Config.TPDB_BASE_URL) or not re.fullmatch(fr'/{section}/\d+', parts.path):
        raise ValueError(f'Enter a TPDb {section} page URL or numeric ID')
    return f'{Config.TPDB_BASE_URL}{parts.path}'


def validate_image_url(url, service):
    if not isinstance(url, str) or any(char.isspace() for char in url) or '\\' in url:
        raise ValueError('Invalid image URL')
    target = origin(url)
    parts = urlsplit(url)
    if service == 'jellyfin':
        base = urlsplit(Config.JELLYFIN_URL)
        prefix = base.path.rstrip('/') + '/Items/'
        if target != origin(Config.JELLYFIN_URL) or not parts.path.startswith(prefix):
            raise ValueError('Jellyfin images must use the configured server')
        if not re.fullmatch(r'[A-Za-z0-9_-]+/Images/Primary(?:/0)?', parts.path[len(prefix):]):
            raise ValueError('Only primary artwork can be proxied')
    elif service == 'tpdb':
        if target not in {origin(Config.TPDB_BASE_URL), ('https', 'images.theposterdb.com', 443)}:
            raise ValueError('Poster images must come from ThePosterDB')
    else:
        raise ValueError('Unknown image service')
    return url


def fetch_image(url, service, headers=None, cookies=None):
    for _ in range(6):
        validate_image_url(url, service)
        if service == 'tpdb' and urlsplit(url).path.startswith('/login'):
            raise ImageLoginRequired('TPDb image download requires a fresh login')
        response = requests.get(url, headers=headers, cookies=cookies, timeout=(5, 30),
                                stream=True, allow_redirects=False)
        try:
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get('Location', ''))
                continue
            if service == 'tpdb' and response.status_code in (401, 403):
                raise ImageLoginRequired('TPDb image download requires a fresh login')
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '').split(';')[0].lower()
            if content_type not in ('image/jpeg', 'image/png', 'image/webp', 'image/avif', 'image/gif'):
                raise ValueError('The server did not return a supported raster image')
            data = bytearray()
            for chunk in response.iter_content(64 * 1024):
                data.extend(chunk)
                if len(data) > MAX_IMAGE_BYTES:
                    raise ValueError('Poster exceeds the 25 MiB download limit')
            return bytes(data), content_type
        finally:
            response.close()
    raise ValueError('Too many image redirects')

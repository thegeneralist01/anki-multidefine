# MultiDefine — shared HTTP helpers

import requests
from http import cookiejar

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
    )
}


class BlockAll(cookiejar.CookiePolicy):
    """Policy to block all cookies."""
    return_ok = set_ok = domain_return_ok = path_return_ok = lambda self, *args, **kwargs: False
    netscape = True
    rfc2965 = hide_cookie2 = False


def _session() -> requests.Session:
    s = requests.Session()
    s.cookies.set_policy(BlockAll())
    return s


def http_get(url: str, *, allow_redirects: bool = True, timeout: int = 10,
             headers: dict = None) -> requests.Response:
    """GET *url* with BlockAll cookie policy. Pass *headers* to override the default."""
    return _session().get(
        url,
        headers=headers if headers is not None else HEADERS,
        allow_redirects=allow_redirects,
        timeout=timeout,
    )


def soup(response: requests.Response):
    """Parse *response* content as BeautifulSoup (html.parser)."""
    # bs4 is vendored relative to the add-on root; callers import it directly.
    from bs4 import BeautifulSoup
    return BeautifulSoup(response.content, 'html.parser')


def fetch_bytes(url: str, timeout: int = 5) -> bytes:
    """Download raw bytes from *url* (e.g. audio files)."""
    return _session().get(url, headers=HEADERS, timeout=timeout).content

# MultiDefine — provider base class and shared helpers

import importlib.util
import os
import pathlib
import sys
import unicodedata
from contextlib import contextmanager
from typing import List, Optional


# ---------------------------------------------------------------------------
# NLTK path helpers (shared; providers and autodefine.py both use this)
# ---------------------------------------------------------------------------

@contextmanager
def add_to_path(p):
    old_path = sys.path
    sys.path = sys.path[:]
    sys.path.insert(0, str(p))
    try:
        yield
    finally:
        sys.path = old_path


def path_import(name: str):
    """Import *name* from the vendored modules/ directory next to this add-on."""
    # Walk up from providers/ to AutoDefineAddon/ then into modules/
    addon_root = pathlib.Path(__file__).parent.parent
    absolute_path = os.path.join(addon_root, 'modules')
    init_file = os.path.join(absolute_path, name, '__init__.py')
    with add_to_path(absolute_path):
        spec = importlib.util.spec_from_file_location(name, init_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module


# ---------------------------------------------------------------------------
# word_info helpers
# ---------------------------------------------------------------------------

def make_sense(
    description: Optional[str],
    examples: List[str],
    extra_example: Optional[List[str]] = None,
) -> dict:
    """Build one sense dict matching the word_info contract."""
    return {
        'description': description,
        'examples': list(examples),
        'extra_example': list(extra_example) if extra_example else [],
    }


def single_group(senses: List[dict], namespace: Optional[str] = None) -> List[dict]:
    """Wrap *senses* in a single namespace group (the definitions list)."""
    return [{'namespace': namespace, 'definitions': senses}]


# ---------------------------------------------------------------------------
# Unicode / normalisation helpers
# ---------------------------------------------------------------------------

def strip_stress(s: str) -> str:
    """Remove combining diacritical marks (U+0300–U+036F) — strips Russian stress marks."""
    return ''.join(
        ch for ch in unicodedata.normalize('NFD', s)
        if not unicodedata.combining(ch)
    )


def snowball_normalize(lang: str):
    """Return a normalize callable using NLTK SnowballStemmer for *lang*."""
    nltk = path_import('nltk')
    stemmer = nltk.stem.SnowballStemmer(lang)

    def _normalize(token: str) -> str:
        t = strip_stress(token).casefold()
        return stemmer.stem(t)

    return _normalize


# ---------------------------------------------------------------------------
# DictionaryProvider
# ---------------------------------------------------------------------------

class DictionaryProvider:
    """Abstract base for all language providers.

    Subclasses MUST set *key* and *display_name* and implement *get_words_info*.
    They MUST NOT import aqt / anki / mw.
    """

    key: str = ''                           # e.g. 'german'
    display_name: str = ''                  # e.g. 'German'
    pronunciation_prefixes: List[str] = []  # priority order; e.g. ['de']

    # Lazily initialised so subclasses don't pay the NLTK load cost at import time.
    _tokenize = None
    _normalize = None

    # --- override these in subclasses as needed ----------------------------

    def get_words_info(self, word: str) -> List[dict]:
        """Fetch and return a list of word_info dicts. Return [] if not found."""
        raise NotImplementedError

    def tokenize(self, text: str) -> List[str]:
        if self._tokenize is None:
            nltk = path_import('nltk')
            type(self)._tokenize = staticmethod(nltk.wordpunct_tokenize)
        return self._tokenize(text)

    def normalize(self, token: str) -> str:
        if self._normalize is None:
            type(self)._normalize = staticmethod(lambda t: strip_stress(t).casefold())
        return self._normalize(token)

# MultiDefine — English provider (Oxford Learner's Dictionaries)
#
# Wraps the unchanged oxford.py scraper (BSD 3-Clause, NearHuscarl) and
# translates its output into the shared word_info contract.
# Oxford-specific orchestration that was previously in autodefine.py
# now lives here so autodefine.py stays language-agnostic.

from __future__ import annotations

import pathlib
import sys
from typing import List, Optional

from .base import DictionaryProvider, path_import, single_group, make_sense


def _oxford_word_module():
    """Import the oxford module from the add-on root (not from providers/)."""
    # We need to import oxford.py which lives in AutoDefineAddon/, one level up.
    addon_root = str(pathlib.Path(__file__).parent.parent)
    if addon_root not in sys.path:
        sys.path.insert(0, addon_root)
    # oxford.py imports bs4 which is vendored in AutoDefineAddon/
    bs4_path = str(pathlib.Path(__file__).parent.parent)
    if bs4_path not in sys.path:
        sys.path.insert(0, bs4_path)
    import importlib
    spec = importlib.util.spec_from_file_location(
        'oxford',
        str(pathlib.Path(__file__).parent.parent / 'oxford.py'),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_oxford = None  # lazy


def _get_oxford():
    global _oxford
    if _oxford is None:
        _oxford = _oxford_word_module()
    return _oxford


# CORPUS → pronunciation_prefixes mapping (matches legacy autodefine.py logic)
_CORPUS_MAP = {
    'british':        ['BrE'],
    'american':       ['nAmE'],
    'british_first':  ['BrE', 'nAmE'],
    'american_first': ['nAmE', 'BrE'],
}

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
    )
}


class OxfordEnglishProvider(DictionaryProvider):
    key = 'english'
    display_name = 'English'

    def __init__(self):
        self._corpus = 'american'
        self.pronunciation_prefixes = ['nAmE']

    def set_corpus(self, corpus: str) -> None:
        self._corpus = corpus.lower()
        self.pronunciation_prefixes = _CORPUS_MAP.get(
            self._corpus, ['nAmE']
        )

    # PorterStemmer for English — same as legacy code.
    def tokenize(self, text: str) -> List[str]:
        nltk = path_import('nltk')
        return nltk.wordpunct_tokenize(text)

    def normalize(self, token: str) -> str:
        nltk = path_import('nltk')
        return nltk.stem.PorterStemmer().stem(token.lower())

    # ------------------------------------------------------------------

    def get_words_info(self, word: str) -> List[dict]:
        oxford = _get_oxford()
        Word = oxford.Word
        WordNotFound = oxford.WordNotFound

        words_info = []
        word_to_search = word.replace(' ', '-').lower()
        try:
            Word.get(word_to_search, _HEADERS, is_search=True)
            raw = Word.info()
            words_info.append(self._translate(raw))

            word_name = raw['name'].lower()
            other_results = raw.get('other_results')
            if other_results:
                for other_result in other_results:
                    all_matches = other_result.get('All matches')
                    if all_matches:
                        for match in all_matches:
                            if word_name == match['name'].strip().lower():
                                try:
                                    Word.get(match['id'], _HEADERS, is_search=False)
                                    raw2 = Word.info()
                                    if raw2['name'].lower() == word_name:
                                        words_info.append(self._translate(raw2))
                                except WordNotFound:
                                    pass
        except WordNotFound:
            pass

        return words_info

    # ------------------------------------------------------------------

    @staticmethod
    def _translate(raw: dict) -> dict:
        """Convert oxford.py Word.info() dict into the shared word_info schema."""
        # verb_forms: extract values from {thirdps, past, pastpart, prespart} dicts
        verb_forms_list: List[str] = []
        vf = raw.get('verb_forms')
        if vf:
            for key in ('thirdps', 'past', 'pastpart', 'prespart'):
                entry = vf.get(key)
                if entry and entry.get('value'):
                    verb_forms_list.append(entry['value'])

        # pronunciations: oxford already emits the right shape
        # {'prefix': 'BrE'/'nAmE', 'ipa': str, 'ogg': str, 'mp3': str}
        pronunciations = raw.get('pronunciations', [])

        # definitions: oxford already uses the same namespace/definitions schema
        definitions = raw.get('definitions', [])

        return {
            'name':           raw.get('name', ''),
            'wordform':       raw.get('wordform'),
            'pronunciations': pronunciations,
            'definitions':    definitions,
            'verb_forms_list': verb_forms_list,
        }

# MultiDefine — provider registry

from __future__ import annotations

from typing import Dict, Optional, Type

from .base import DictionaryProvider

# Import all concrete providers so PROVIDERS is populated.
from .english_oxford import OxfordEnglishProvider
from .german_dwds import DWDSGermanProvider
from .russian_wiktionary import WiktionaryRussianProvider
from .french_larousse import LarousseFrencProvider
from .azerbaijani_azleks import AzleksAzerbaijaniProvider

PROVIDERS: Dict[str, Type[DictionaryProvider]] = {
    'english':    OxfordEnglishProvider,
    'german':     DWDSGermanProvider,
    'russian':    WiktionaryRussianProvider,
    'french':     LarousseFrencProvider,
    'azerbaijani': AzleksAzerbaijaniProvider,
}


def build_provider(key: str, lang_cfg: dict) -> Optional[DictionaryProvider]:
    """Instantiate and return the provider for *key*, or None if unknown."""
    cls = PROVIDERS.get(key)
    if cls is None:
        return None
    provider = cls()
    # English provider needs the corpus setting.
    if hasattr(provider, 'set_corpus'):
        provider.set_corpus(lang_cfg.get('corpus', 'American'))
    return provider

# MultiDefine — Russian provider (ru.wiktionary)
# Source: https://ru.wiktionary.org  (MediaWiki parse API, no key)
#
# Wiktionary HTML structure (2024+):
#   Language sections:  <div class="mw-heading mw-heading1"><h1>Русский</h1></div>
#   Subsections:        <div class="mw-heading mw-heading3"><h3>Значение</h3></div>
#   Examples:           <span class="example-block"> inside <li> in the meaning <ol>
#   IPA:                <span class="IPA"> in the pronunciation section

from __future__ import annotations

import copy
import re
from typing import List, Optional, Tuple
from urllib.parse import quote

from .base import DictionaryProvider, make_sense, single_group, strip_stress, snowball_normalize
from . import net

_RUSSIAN_POS = {
    'Существительное', 'Глагол', 'Прилагательное', 'Наречие',
    'Местоимение', 'Причастие', 'Числительное', 'Деепричастие',
    'Предлог', 'Союз', 'Частица', 'Междометие',
}


class WiktionaryRussianProvider(DictionaryProvider):
    key = 'russian'
    display_name = 'Russian'
    pronunciation_prefixes = ['ru']

    def normalize(self, token: str) -> str:
        if not hasattr(self, '_norm'):
            base = snowball_normalize('russian')
            self._norm = lambda t: base(strip_stress(t))
        return self._norm(token)

    # ------------------------------------------------------------------

    def get_words_info(self, word: str) -> List[dict]:
        # Try exact case first, then lowercase (Wiktionary is case-sensitive
        # on the first letter; users may type in all-caps).
        result = self._fetch(word)
        if not result and word != word.lower():
            result = self._fetch(word.lower())
            if result:
                result[0]['name'] = word  # preserve original capitalisation
        return result

    def _fetch(self, word: str) -> List[dict]:
        url = (
            'https://ru.wiktionary.org/w/api.php'
            f'?action=parse&page={quote(word)}&format=json&prop=text'
        )
        _wiki_headers = {
            'User-Agent': (
                'MultiDefine/1.0 (Anki add-on; '
                'https://github.com/thegeneralist/anki-multi-language-auto-define)'
            )
        }
        response = net.http_get(url, headers=_wiki_headers)
        if response.status_code == 403:
            raise RuntimeError(
                'Wiktionary rate-limited this request (HTTP 403). '
                'Wait a moment and try again.'
            )
        if response.status_code != 200:
            return []

        try:
            payload = response.json()
        except Exception:
            return []

        if 'error' in payload or 'parse' not in payload:
            return []

        html = payload['parse']['text']['*']
        from bs4 import BeautifulSoup
        full_bs = BeautifulSoup(html, 'html.parser')

        section = _find_russian_section(full_bs)
        if section is None:
            return []

        name = word
        wordform = _parse_wordform(section)
        ipa, mp3_url, ogg_url = _parse_pronunciation(section)
        senses = _parse_senses(section)

        if not senses:
            return []

        return [{
            'name':           name,
            'wordform':       wordform,
            'pronunciations': [{
                'prefix':     'ru',
                'ipa':        ipa,
                'mp3':        mp3_url,
                'ogg':        ogg_url,
                'audio_name': None,
            }],
            'definitions':    single_group(senses),
            'verb_forms_list': [],
        }]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _find_russian_section(bs):
    """Return a BeautifulSoup wrapping only the Russian language section.

    Language sections are wrapped in <div class="mw-heading mw-heading1">.
    Uses find/find_all only (no CSS selectors; avoids soupsieve dependency).
    """
    from bs4 import BeautifulSoup

    # Prefer the main content div but fall back to the whole soup
    output_div = bs.find(class_='mw-parser-output') or bs

    # Find the div.mw-heading1 whose h1 text is 'Русский'
    russian_wrapper = None
    for div in output_div.find_all('div', class_='mw-heading1'):
        if 'Русский' in div.get_text():
            russian_wrapper = div
            break

    if russian_wrapper is None:
        return None

    # Collect all subsequent siblings until the next mw-heading1
    parts: List[str] = []
    for sib in russian_wrapper.find_next_siblings():
        classes = sib.get('class') or []
        if 'mw-heading1' in classes:
            break
        parts.append(str(sib))

    if not parts:
        return None

    return BeautifulSoup('<div>' + ''.join(parts) + '</div>', 'html.parser')


def _parse_wordform(section) -> Optional[str]:
    """Extract POS from section headings (h3/h4 inside mw-heading3/4 wrappers)."""
    for h in section.find_all(['h3', 'h4']):
        text = h.get_text(strip=True)
        if text in _RUSSIAN_POS:
            return text
    return None


def _parse_pronunciation(section) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    ipa: Optional[str] = None
    mp3_url: Optional[str] = None
    ogg_url: Optional[str] = None

    # First IPA span in the section
    for span in section.find_all('span', class_='IPA'):
        ipa = span.get_text(strip=True)
        break

    # Audio sources
    for source in section.find_all('source'):
        src = source.get('src', '')
        if not src:
            continue
        if src.startswith('//'):
            src = 'https:' + src
        t = source.get('type', '')
        if 'ogg' in t and ogg_url is None:
            ogg_url = src
        elif 'mpeg' in t and mp3_url is None:
            mp3_url = src

    return ipa, mp3_url, ogg_url


def _parse_senses(section) -> List[dict]:
    """Find the Значение subsection and parse its <ol> as senses."""
    # Find the h3 (or h4) containing 'Значение'
    # It lives inside a div.mw-heading.mw-heading3
    meaning_ol = None
    for h in section.find_all(['h3', 'h4']):
        if 'Значение' in h.get_text():
            # The <ol> is a next sibling of the heading's parent div
            parent_wrapper = h.parent  # div.mw-heading.mw-heading3
            for candidate in parent_wrapper.find_next_siblings():
                if candidate.name == 'ol':
                    meaning_ol = candidate
                    break
                # Stop at the next same-level or higher heading div
                classes = candidate.get('class') or []
                if any(c in classes for c in ('mw-heading2', 'mw-heading1')):
                    break
            break

    if meaning_ol is None:
        # Fallback: any ol in the section
        meaning_ol = section.find('ol')

    if meaning_ol is None:
        return []

    senses: List[dict] = []
    for li in meaning_ol.find_all('li', recursive=False):
        # Extract examples from .example-block spans first
        examples: List[str] = [
            s.get_text(' ', strip=True)
            for s in li.find_all('span', class_='example-block')
        ]

        # Build description without noise spans (deep-copy via re-parse avoids
        # bs4 shallow-copy issues where decompose() mutates the original tree)
        li_html = str(li)
        from bs4 import BeautifulSoup as _BS
        li_clone = _BS(li_html, 'html.parser')
        for noise in li_clone.find_all(class_=['example-fullblock', 'example-block', 'mw-editsection']):
            noise.decompose()

        description = li_clone.get_text(' ', strip=True)
        description = re.sub(r'^\d+\.\s*', '', description).strip() or None

        if description or examples:
            senses.append(make_sense(description, examples))

    return senses

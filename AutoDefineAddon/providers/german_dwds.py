# MultiDefine — German provider (DWDS)
# Source: https://www.dwds.de  (no API key, HTML scrape)

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote

from .base import DictionaryProvider, make_sense, single_group, snowball_normalize
from . import net

# Known POS terms in DWDS grammar blocks
_POS_TERMS = {
    'substantiv': 'Substantiv',
    'verb':       'Verb',
    'adjektiv':   'Adjektiv',
    'adverb':     'Adverb',
    'präposition':'Präposition',
    'konjunktion':'Konjunktion',
    'artikel':    'Artikel',
    'pronomen':   'Pronomen',
}


def _clean_name(raw: str) -> str:
    """Strip article/gender suffixes (', der', ', die', ', das', etc.)."""
    # DWDS headings often: "Haus, das" or "Häuser, Plural"
    return raw.split(',')[0].strip()


def _extract_pos(bs) -> Optional[str]:
    """Find the POS label from the DWDS grammar/Wortart block."""
    # Try the explicit "Wortart" label first
    for label_el in bs.select('span.dwdswb-ft-blocklabel'):
        if 'wortart' in label_el.get_text(strip=True).lower():
            sib = label_el.find_next_sibling('span')
            if sib:
                return sib.get_text(strip=True) or None

    # Second pass: look for any label whose sibling text contains a known POS
    for label_el in bs.select('span.dwdswb-ft-blocklabel'):
        sib = label_el.find_next_sibling('span')
        if sib:
            text = sib.get_text(strip=True).lower()
            for key, display in _POS_TERMS.items():
                if key in text:
                    return display

    # Last resort: look for POS keywords in any grammar-block text
    for block in bs.select('span.dwdswb-ft-blocktext'):
        text = block.get_text(strip=True).lower()
        for key, display in _POS_TERMS.items():
            if text.startswith(key):
                return display

    return None


def _parse_verb_forms(bs, name: str) -> List[str]:
    """Extract irregular verb forms from the grammar block."""
    forms: List[str] = []
    for label_el in bs.select('span.dwdswb-ft-blocklabel'):
        if 'grammatik' in label_el.get_text(strip=True).lower():
            block = label_el.find_next_sibling('span')
            if block:
                gram_text = block.get_text(' ', strip=True)
                # DWDS grammar text for verbs: "geht, ging, ist gegangen" or
                # "Verb · geht / ging / ist gegangen"
                # Strip leading "Verb ·" or similar prefix
                gram_text = re.sub(r'^(Verb\s*[·•]\s*)', '', gram_text).strip()
                # Split on comma, semicolon, or " / "
                parts = re.split(r'\s*/\s*|[,;]', gram_text)
                for p in parts:
                    form = p.strip()
                    if not form:
                        continue
                    # Skip if it's just the bare infinitive or article-like text
                    if form.lower() == name.lower():
                        continue
                    # Skip bracketed or parenthetical notes
                    if form.startswith('(') or form.startswith('['):
                        continue
                    forms.append(form)
            break
    return forms


class DWDSGermanProvider(DictionaryProvider):
    key = 'german'
    display_name = 'German'
    pronunciation_prefixes = ['de']

    def normalize(self, token: str) -> str:
        if not hasattr(self, '_norm'):
            self._norm = snowball_normalize('german')
        return self._norm(token)

    # ------------------------------------------------------------------

    def get_words_info(self, word: str) -> List[dict]:
        url = f'https://www.dwds.de/wb/{quote(word, safe="")}'
        response = net.http_get(url)
        if response.status_code == 404:
            return []

        bs = net.soup(response)

        # Headword: prefer the lemmaansatz span
        name_tag = bs.select_one('h1.dwdswb-lemma span.dwdswb-ft-lemmaansatz') \
                   or bs.select_one('h1.dwdswb-lemma') \
                   or bs.select_one('h1')
        raw_name = name_tag.get_text(strip=True) if name_tag else word
        name = _clean_name(raw_name)
        # Strip superscript homograph digits
        name = re.sub(r'[\u00B9\u00B2\u00B3\u2070-\u2079]+$', '', name).strip()

        wordform = _extract_pos(bs)

        # IPA
        ipa_tag = bs.select_one('span.dwdswb-ipa')
        ipa: Optional[str] = ipa_tag.get_text(strip=True) if ipa_tag else None
        if ipa:
            ipa = ipa.strip('/[]').strip()

        # Audio mp3
        audio_tag = bs.select_one('div.dwdswb-ft-blocktext audio source[type="audio/mpeg"]') \
                    or bs.select_one('audio source[type="audio/mpeg"]')
        mp3_url: Optional[str] = None
        if audio_tag and audio_tag.get('src'):
            mp3_url = audio_tag['src']
            if mp3_url.startswith('//'):
                mp3_url = 'https:' + mp3_url

        verb_forms_list = _parse_verb_forms(bs, name)

        # Senses
        senses = self._parse_senses_per_lesart(bs, name) or \
                 self._parse_senses_overview(bs, name)

        if not senses:
            return []

        return [{
            'name':           name,
            'wordform':       wordform,
            'pronunciations': [{'prefix': 'de', 'ipa': ipa, 'mp3': mp3_url, 'ogg': None,
                                'audio_name': None}],
            'definitions':    single_group(senses),
            'verb_forms_list': verb_forms_list,
        }]

    # ------------------------------------------------------------------

    def _parse_senses_per_lesart(self, bs, name: str) -> List[dict]:
        senses = []
        for lesart in bs.select('.dwdswb-lesart'):
            def_tag = lesart.select_one('.dwdswb-definition') \
                      or lesart.select_one('.dwdswb-definitionen')
            description: Optional[str] = def_tag.get_text(' ', strip=True) if def_tag else None

            examples: List[str] = []
            for ex_tag in lesart.select('span.dwdswb-belegtext'):
                examples.append(ex_tag.get_text(' ', strip=True))

            if description or examples:
                senses.append(make_sense(description, examples))
        return senses

    def _parse_senses_overview(self, bs, name: str) -> List[dict]:
        senses = []
        glosses: List[str] = []
        for li in bs.select('div.bedeutungsuebersicht ol li'):
            t = li.get_text(' ', strip=True)
            if t:
                glosses.append(t)

        if not glosses:
            for item in bs.select('.dwdswb-kompakt-definition'):
                t = item.get_text(' ', strip=True)
                if t:
                    glosses.append(t)

        all_examples: List[str] = [
            tag.get_text(' ', strip=True)
            for tag in bs.select('span.dwdswb-belegtext')
        ]

        n = max(len(glosses), 1)
        chunk = max(len(all_examples) // n, 1)
        for i, gloss in enumerate(glosses):
            exs = all_examples[i * chunk:(i + 1) * chunk]
            senses.append(make_sense(gloss, exs))

        if not senses and all_examples:
            senses.append(make_sense(None, all_examples))

        return senses

# MultiDefine — Azerbaijani provider (AZLEKS)
# Source: https://azleks.az  (two-step: search → entry page, HTML scrape)

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote_plus, urljoin

from .base import DictionaryProvider, make_sense, single_group, strip_stress
from . import net

_BASE = 'https://azleks.az'


class AzleksAzerbaijaniProvider(DictionaryProvider):
    key = 'azerbaijani'
    display_name = 'Azerbaijani'
    pronunciation_prefixes = ['az']

    def normalize(self, token: str) -> str:
        return strip_stress(token).casefold()

    # ------------------------------------------------------------------

    def get_words_info(self, word: str) -> List[dict]:
        search_url = f'{_BASE}/dictionary?search={quote_plus(word)}&dictionary_id=4'
        resp = net.http_get(search_url)
        if resp.status_code != 200:
            return []

        bs = net.soup(resp)
        entry_href = self._find_entry_href(bs, word)
        if not entry_href:
            return []

        entry_url = urljoin(_BASE, entry_href) if not entry_href.startswith('http') else entry_href
        resp2 = net.http_get(entry_url)
        if resp2.status_code != 200:
            return []

        return self._parse_entry(net.soup(resp2), word)

    # ------------------------------------------------------------------

    def _find_entry_href(self, bs, word: str) -> Optional[str]:
        """Return the href for an exact headword match, or None.

        AZLEKS search result links contain the full entry text
        (headword + [phonetics] + POS + senses).  Extract the headword
        as the text before the first '[' bracket.
        """
        for item in bs.select('.dictionary-list .dictionary-item'):
            a = item.select_one('a[href]')
            if a is None:
                continue
            full_text = a.get_text(strip=True)
            # Headword is the portion before the phonetic brackets
            headword = full_text.split('[')[0].strip()
            if headword.lower() == word.lower():
                return a['href']
        return None  # No fallback — exact match only

    def _parse_entry(self, bs, word: str) -> List[dict]:
        info_div = bs.select_one('.dictionary-info') or bs

        # Headword: strip nested .teleffuz / .nitq-hissesi from h3
        name_tag = info_div.select_one('h3.bash-soz') or info_div.select_one('h3')
        if name_tag:
            import copy
            name_clone = copy.copy(name_tag)
            for noise in name_clone.find_all(class_=['teleffuz', 'nitq-hissesi', 'etimologiya']):
                noise.decompose()
            name = name_clone.get_text(strip=True) or word
        else:
            name = word

        pos_tag = info_div.select_one('.nitq-hissesi')
        wordform: Optional[str] = pos_tag.get_text(strip=True) if pos_tag else None

        tel_tag = info_div.select_one('.teleffuz')
        ipa: Optional[str] = tel_tag.get_text(strip=True) if tel_tag else None

        senses = self._parse_senses(info_div, name)

        if not senses:
            return []

        return [{
            'name':           name,
            'wordform':       wordform,
            'pronunciations': [{
                'prefix':     'az',
                'ipa':        ipa,
                'mp3':        None,
                'ogg':        None,
                'audio_name': None,
            }],
            'definitions':    single_group(senses),
            'verb_forms_list': [],
        }]

    def _parse_senses(self, info_div, name: str) -> List[dict]:
        """
        Entry page structure (confirmed live):
          <p>
            <strong>1</strong><strong>.</strong> definition □ <em>example</em><br/>
            <strong>2.</strong> definition □ <em>example</em><br/>
          </p>
          <p>Həmçinin bax:</p>   ← see-also, ignored

        Strategy: find the main <p>, split children on numbered <strong> markers,
        then within each group split on □ for description vs. examples.
        """
        from bs4 import NavigableString, Tag

        # Find the first content paragraph (skip "Həmçinin bax")
        main_p = None
        for p in info_div.select('p'):
            if 'Həmçinin' not in p.get_text():
                main_p = p
                break

        if main_p is None:
            return []

        children = list(main_p.children)

        # Split children into sense groups at <strong>N.</strong> markers.
        # Sense 1 may use two separate <strong> tags: <strong>1</strong><strong>.</strong>
        # Sense 2+ use a single tag:              <strong>2.</strong>
        def _is_number_strong(node) -> bool:
            return (isinstance(node, Tag) and node.name == 'strong'
                    and bool(re.match(r'^\d+$', node.get_text(strip=True))))

        def _is_dot_strong(node) -> bool:
            return (isinstance(node, Tag) and node.name == 'strong'
                    and node.get_text(strip=True) == '.')

        def _is_combined_marker(node) -> bool:
            return (isinstance(node, Tag) and node.name == 'strong'
                    and bool(re.match(r'^\d+\.$', node.get_text(strip=True))))

        groups: List[List] = []
        current: List = []
        i = 0
        while i < len(children):
            child = children[i]
            next_child = children[i + 1] if i + 1 < len(children) else None

            if _is_combined_marker(child):
                if current:
                    groups.append(current)
                current = []
                i += 1
            elif _is_number_strong(child) and _is_dot_strong(next_child):
                if current:
                    groups.append(current)
                current = []
                i += 2  # skip both <strong>N</strong> and <strong>.</strong>
            else:
                current.append(child)
                i += 1

        if current:
            groups.append(current)

        senses = []
        for group in groups:
            sense = self._extract_sense_from_group(group)
            if sense['description'] or sense['examples']:
                senses.append(sense)

        return senses

    def _extract_sense_from_group(self, nodes) -> dict:
        """Extract description + examples from a list of BeautifulSoup nodes.

        Description = text/inline content before the □ separator.
        Examples    = <em> content after □.
        """
        from bs4 import NavigableString, Tag

        description_parts: List[str] = []
        examples: List[str] = []
        past_square = False

        for node in nodes:
            if isinstance(node, NavigableString):
                text = str(node)
                if '□' in text or '\u25a1' in text:
                    before, _, after = text.partition('□') if '□' in text else text.partition('\u25a1')
                    description_parts.append(before)
                    past_square = True
                    if after.strip():
                        examples.append(after.strip())
                elif not past_square:
                    description_parts.append(text)
            elif isinstance(node, Tag):
                if node.name == 'em':
                    if past_square:
                        examples.append(node.get_text(' ', strip=True))
                    else:
                        description_parts.append(node.get_text(' ', strip=True))
                elif node.name in ('br', 'strong'):
                    pass  # structural; skip
                else:
                    t = node.get_text(' ', strip=True)
                    if t and not past_square:
                        description_parts.append(t)

        description = ' '.join(description_parts).strip() or None
        return make_sense(description, [e for e in examples if e])

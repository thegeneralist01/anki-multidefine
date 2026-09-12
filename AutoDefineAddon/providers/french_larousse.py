# MultiDefine — French provider (Larousse)
# Source: https://www.larousse.fr/dictionnaires/francais/{word}  (HTML scrape)

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote, urljoin

from .base import DictionaryProvider, make_sense, single_group, snowball_normalize
from . import net


class LarousseFrencProvider(DictionaryProvider):
    key = 'french'
    display_name = 'French'
    pronunciation_prefixes = ['fr']

    def normalize(self, token: str) -> str:
        if not hasattr(self, '_norm'):
            self._norm = snowball_normalize('french')
        return self._norm(token)

    # ------------------------------------------------------------------

    def get_words_info(self, word: str) -> List[dict]:
        url = f'https://www.larousse.fr/dictionnaires/francais/{quote(word)}'
        response = net.http_get(url)
        if response.status_code == 404:
            return []

        # Use final URL after redirect to determine canonical slug
        final_url = response.url
        bs = net.soup(response)

        # Handle disambiguation: if we land on a page with multiple headwords
        # and ours is not the primary, follow the first exact-match link.
        bs = self._maybe_follow_disambiguation(bs, word, final_url)
        if bs is None:
            return []

        results = []
        # Each article.BlocDefinition.content contains one POS group
        article = bs.select_one('#definition article.BlocDefinition.content') \
                   or bs.select_one('article.BlocDefinition') \
                   or bs.select_one('#definition')

        if article is None:
            return []

        # Name: first AdresseDefinition
        name_tag = article.select_one('h2.AdresseDefinition') or article.select_one('.AdresseDefinition')
        import unicodedata
        name = name_tag.get_text(strip=True) if name_tag else word
        # Strip private-use Unicode chars (webfont icons) and trailing digits
        name = ''.join(c for c in name if unicodedata.category(c) != 'Co')
        name = re.sub(r'[\d\s]+$', '', name).strip()

        # Audio: first audio element
        audio_tag = article.select_one('audio[src]') or article.select_one('h2.AdresseDefinition audio[src]')
        mp3_url: Optional[str] = None
        audio_name: Optional[str] = None
        if audio_tag:
            src = audio_tag.get('src', '')
            if src:
                mp3_url = urljoin('https://www.larousse.fr/', src)
                # Larousse URLs may have no extension — force .mp3
                slug = final_url.rstrip('/').split('/')[-1]
                if not any(mp3_url.endswith(ext) for ext in ('.mp3', '.ogg', '.wav')):
                    audio_name = f'{slug}.mp3'

        # Iterate POS blocks (Zone-Entree1 header-article or Zone-Entree header-article)
        pos_blocks = article.select('.Zone-Entree1.header-article, .Zone-Entree.header-article')
        if not pos_blocks:
            # Try to get a single block
            pos_blocks = [article]

        all_senses: List[dict] = []
        wordform: Optional[str] = None

        for pos_block in pos_blocks:
            # POS label
            cat_tag = pos_block.select_one('p.CatgramDefinition') \
                      or pos_block.select_one('.CatgramDefinition')
            if cat_tag and wordform is None:
                wordform = cat_tag.get_text(strip=True) or None

            # Find associated ul.Definitions (sibling or within next block)
            ul = pos_block.find_next_sibling('ul', class_='Definitions') \
                 or pos_block.select_one('ul.Definitions')

            if ul is None:
                continue

            for li in ul.select('li.DivisionDefinition'):
                import copy
                li_clone = copy.copy(li)

                # Examples
                examples: List[str] = [
                    ex.get_text(' ', strip=True)
                    for ex in li.select('span.ExempleDefinition')
                ]

                # Remove synonym/related blocks before extracting description
                for noise in li_clone.select('p.LibelleSynonyme, p.Synonymes, '
                                             'span.ExempleDefinition, .BlocSynonyme'):
                    noise.decompose()

                raw = li_clone.get_text(' ', strip=True)
                description = re.sub(r'^\s*\d+\.\s*', '', raw).strip() or None

                all_senses.append(make_sense(description, examples))

        if not all_senses:
            return []

        results.append({
            'name':           name,
            'wordform':       wordform,
            'pronunciations': [{
                'prefix':     'fr',
                'ipa':        None,
                'mp3':        mp3_url,
                'ogg':        None,
                'audio_name': audio_name,
            }],
            'definitions':    single_group(all_senses),
            'verb_forms_list': [],
        })
        return results

    # ------------------------------------------------------------------

    def _maybe_follow_disambiguation(self, bs, word: str, base_url: str):
        """If we're on a disambiguation page, follow the first exact-headword entry."""
        # Larousse disambiguation pages have .BlocChoix or similar
        # For now: check if #definition exists; if not, look for a link
        if bs.select_one('#definition'):
            return bs
        # Look for a link containing the word in the path
        for a in bs.select('a[href]'):
            href = a.get('href', '')
            text = a.get_text(strip=True).lower()
            if word.lower() in text and '/dictionnaires/francais/' in href:
                url = urljoin(base_url, href)
                r2 = net.http_get(url)
                if r2.status_code == 200:
                    return net.soup(r2)
        return bs  # best effort

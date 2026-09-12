# AGENTS.md — MultiDefine contributor context

This file is authoritative context for AI agents working on this codebase.
Read it fully before making any changes.

---

## Project overview

**MultiDefine** is an Anki add-on that auto-defines words from monolingual
dictionaries in multiple languages. It fills note fields with definitions,
clozed examples, audio, IPA phonetics, and verb forms.

Based on [AutoDefine Oxford Learner's Dictionaries](https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries)
by Artem Petrov (GPL v2). English behavior is preserved bit-for-bit.

---

## Repository layout

```
AutoDefineAddon/          ← the actual Anki add-on package
  __init__.py             ← Anki entry point; imports autodefine
  autodefine.py           ← orchestration, UI, Anki integration
  oxford.py               ← upstream Oxford scraper (BSD 3-Clause, NearHuscarl) — do not modify
  config.json             ← default user config
  config.md               ← config documentation shown in Anki
  bs4/                    ← vendored BeautifulSoup 4.11.1 (no soupsieve)
  modules/nltk/           ← vendored NLTK (SnowballStemmer, PorterStemmer, wordpunct_tokenize)
  images/                 ← add-on icon
  webbrowser/             ← vendored webbrowser module
  providers/
    __init__.py           ← PROVIDERS registry + build_provider()
    net.py                ← shared HTTP helpers (http_get, soup, fetch_bytes)
    base.py               ← DictionaryProvider ABC, word_info helpers, path_import
    english_oxford.py     ← wraps oxford.py
    german_dwds.py        ← DWDS scraper
    russian_wiktionary.py ← ru.Wiktionary MediaWiki API
    french_larousse.py    ← Larousse scraper
    azerbaijani_azleks.py ← AZLEKS two-step scraper
scripts/
  check_providers.py      ← standalone smoke-test (no Anki needed)
  build_ankiaddon.sh      ← builds multidefine.ankiaddon for AnkiWeb upload
```

---

## Hard rules

1. **Providers must never import `anki`, `aqt`, or `mw`.**
   They must be importable and testable without Anki installed.

2. **`oxford.py` is untouched upstream code.** Do not modify it.
   `english_oxford.py` wraps it.

3. **All Anki integration lives in `autodefine.py`.**
   Providers return data; `autodefine.py` writes to notes and downloads audio.

4. **Providers return URLs; `autodefine.py` downloads audio.**
   Never write to `collection.media` from a provider.

5. **The vendored bs4 4.11.1 has no soupsieve.**
   Never use `.select()` or `.select_one()` in provider code — use
   `.find()` and `.find_all()` only. CSS selectors raise `NotImplementedError`
   with the vendored bs4.

---

## word_info contract

Every provider's `get_words_info(word)` returns `list[dict]` where each dict is:

```python
{
  'name': str,                    # resolved headword
  'wordform': Optional[str],      # POS label (italic in output), or None
  'pronunciations': [
    {
      'prefix': str,              # must match one of provider.pronunciation_prefixes
      'ipa': Optional[str],       # phonetic text without surrounding slashes/brackets
      'mp3': Optional[str],       # absolute URL or None
      'ogg': Optional[str],       # absolute URL or None
      'audio_name': Optional[str] # explicit filename, or None → derive from URL
    }
  ],
  'definitions': [                # list of namespace groups
    {
      'namespace': Optional[str],
      'definitions': [
        {
          'description': Optional[str],
          'examples': [str],
          'extra_example': [str]
        }
      ]
    }
  ],
  'verb_forms_list': [str],       # inflected forms; may be []
}
```

Use `make_sense(description, examples)` and `single_group(senses)` from
`providers/base.py` to build these structures.

---

## Adding a new language

1. Create `AutoDefineAddon/providers/<lang>.py`:
   - Subclass `DictionaryProvider` from `providers/base.py`
   - Set `key`, `display_name`, `pronunciation_prefixes`
   - Implement `get_words_info(word) -> list[dict]`
   - Use `net.http_get(url)` and `net.soup(response)` for HTTP
   - Do **not** use `.select()` / `.select_one()` (no soupsieve)

2. Register in `providers/__init__.py`:
   ```python
   from .my_lang import MyLangProvider
   PROVIDERS['mylang'] = MyLangProvider
   ```

3. Add an entry to `config.json` under `4. languages`:
   ```json
   { "key": "mylang", "enabled": true, "display_name": "My Language",
     "note_type": "MultiDefine_MyLanguage", "max_examples": 2, "max_definitions": 3 }
   ```

4. Add a test case in `scripts/check_providers.py`.

---

## Wikimedia / Wiktionary User-Agent

Wikimedia blocks the shared `net.HEADERS` Chrome User-Agent with HTTP 403
("Too many requests. Please respect our robot policy.").

For any request to `*.wikimedia.org` or `*.wiktionary.org`, use a
descriptive User-Agent:

```python
_WIKI_HEADERS = {
    'User-Agent': (
        'MultiDefine/1.0 (Anki add-on; '
        'https://github.com/thegeneralist01/anki-multidefine)'
    )
}
response = net.http_get(url, headers=_WIKI_HEADERS)
```

This is already done in `russian_wiktionary.py`. Apply the same pattern
to any future Wikimedia-hosted source.

---

## bs4 import discipline

In Anki's environment, `AutoDefineAddon/` is prepended to `sys.path`.
The vendored `bs4/` is therefore the first `bs4` found.

- Always import via `net.soup(response)` when parsing HTTP responses.
- If you must import `BeautifulSoup` directly (e.g. to parse a string),
  do so at the **top of the module** (not inside functions), so the import
  resolves once and consistently.
- The vendored bs4 4.11.1 supports `find()`, `find_all()`, `get_text()`,
  `get()`, `parent`, `find_next_siblings()` — all without soupsieve.

---

## Config schema

```
0. test mode    → TEST_MODE
0. general      → USE_DEFAULT_TEMPLATE, CLEAN_HTML_IN_SOURCE_FIELD, REPLACE_BY
1. fields       → SOURCE_FIELD … IMAGE_FIELD  (0-indexed)
2. image        → OPEN_IMAGES_IN_BROWSER, SEARCH_APPEND, OPEN_IMAGES_IN_BROWSER_LINK
3. shortcuts    → PRIMARY_SHORTCUT
4. languages    → ordered array of language objects (drives popup order + keybinds 1–N)
```

Field indices are **shared across all languages**. The note type fields
(Word / DefinitionAndExamples / Audio / Phonetics / VerbForms / Image)
are language-agnostic.

---

## Cloze mechanics

`REPLACE_BY` (default `#$#`) is the cloze template. `$` is replaced by
the matched token. The card template renders `#word#` → **word** on the
back, and `#word#` → `____` in the reverse/cloze template.

`replace_word_in_sentence` uses `provider.tokenize` + `provider.normalize`
to match headword and verb forms in examples. When no match is found, the
example is included as plain text (no red indicator). The
`MultiDefine_WordNotReplaced` tag is set on the note as a soft signal.

---

## Running the standalone test

```bash
# Requires network + requests + beautifulsoup4
python3 scripts/check_providers.py
```

All 6/6 checks must pass before merging any provider change.

---

## Building the add-on package

```bash
bash scripts/build_ankiaddon.sh
# → multidefine.ankiaddon (ignored by git)
```

Upload to AnkiWeb or attach to a GitHub Release. The package contains only
`AutoDefineAddon/` contents — no `scripts/`, `README.md`, or other repo files.

---

## Known gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| Russian returns `[]` in Anki, works standalone | Wikimedia HTTP 403 | Use Wikimedia-compliant User-Agent |
| `NotImplementedError: CSS selectors cannot be used` | `.select()` called with vendored bs4 | Replace with `.find()` / `.find_all()` |
| `AttributeError: QDialog has no attribute 'Accepted'` | PyQt6 enum path changed | Use `QDialog.DialogCode.Accepted` |
| `AttributeError: Qt has no attribute 'Key_1'` | PyQt6 enum path changed | Use `Qt.Key.Key_1` |
| Audio filename percent-encoded (e.g. `Ru-%D1%83...`) | URL not decoded | `urllib.parse.unquote(filename)` |
| Error tooltip immediately overwritten | Support tooltip shown unconditionally | Only show support tooltip on success |

---

## Licenses

- `autodefine.py`, `providers/`: GPL v2 (derivative of Artem Petrov's work)
- `oxford.py`: BSD 3-Clause (NearHuscarl)
- `bs4/`: MIT
- `modules/nltk/`: Apache 2.0

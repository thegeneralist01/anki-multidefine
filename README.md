# MultiDefine

An Anki add-on that auto-defines words from monolingual dictionaries in multiple languages — English, German, Russian, French, and Azerbaijani — and fills note fields with definitions, examples (headword clozed), audio, phonetics, and verb forms.

Based on [AutoDefine Oxford Learner's Dictionaries](https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries) by Artem Petrov. English behavior is preserved bit-for-bit.

---

## Languages & Sources

| Language | Source | Definitions | Audio | IPA | Verb forms |
|----------|--------|-------------|-------|-----|------------|
| English | Oxford Learner's Dictionaries | ✓ | ✓ mp3 | ✓ | ✓ |
| German | DWDS | ✓ native | ✓ mp3 | most words | ✓ irregular |
| Russian | ru.Wiktionary | ✓ native | ✓ ogg+mp3 | ✓ | — |
| French | Larousse | ✓ native | ✓ mp3 | — | — |
| Azerbaijani | AZLEKS | ✓ native | — | bracketed | — |

No API key required. All sources are scraped directly.

---

## Installation

1. Clone or download this repo.
2. Symlink `AutoDefineAddon/` into your Anki add-ons folder:
   ```bash
   ln -s /path/to/repo/AutoDefineAddon \
     ~/Library/Application\ Support/Anki2/addons21/multidefine
   ```
3. Restart Anki.

---

## Usage

1. Open **Add Cards**.
2. Type a word in the Word field.
3. Click the **MultiDefine** button or press `Ctrl+Alt+Shift+D`.
4. Choose a language from the popup (or press `1`–`5`).

The add-on fills:
- **DefinitionAndExamples** — definitions + examples with the headword clozed as `#word#`
- **Audio** — `[sound:…]` tag
- **Phonetics** — IPA transcription
- **VerbForms** — conjugated/inflected forms
- Opens a Google image search for the word

**Bulk define:** Browser → select notes → Edit → *MultiDefine in bulk…*

---

## Configuration

Edit the add-on config via **Tools → Add-ons → MultiDefine → Config**.

Key options:

- `4. languages` — ordered list of enabled languages; controls popup order and `1`–`N` keybinds
- `enabled: false` — hide a language without removing it
- `max_examples` / `max_definitions` — limits per sense (`false` = unlimited)
- `corpus` — English only: `"American"`, `"British"`, `"American_first"`, `"British_first"`

See [`AutoDefineAddon/config.md`](AutoDefineAddon/config.md) for full documentation.

---

## Adding a new language

1. Write `AutoDefineAddon/providers/<lang>.py` with a class extending `DictionaryProvider`.
2. Register it in `AutoDefineAddon/providers/__init__.py`.
3. Add an entry to `4. languages` in `config.json`.

The provider must implement `get_words_info(word) -> list[dict]` and must not import `anki`/`aqt`.

---

## License

GPL v2 — see individual files for attribution.  
`oxford.py` is BSD 3-Clause © NearHuscarl.

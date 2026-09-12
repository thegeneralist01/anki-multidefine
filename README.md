# MultiDefine

An Anki add-on that auto-defines words from monolingual dictionaries in multiple languages — English, German, Russian, French, and Azerbaijani — and fills note fields with definitions, examples (headword clozed for study), audio, phonetics, and verb forms.

Based on [AutoDefine Oxford Learner's Dictionaries](https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries) by Artem Petrov. English behavior is preserved bit-for-bit.

---

## Install

**Tools → Add-ons → Get Add-ons → paste code:**

```
755799523
```

Restart Anki. Done.

---

## Languages & sources

| Language | Source | Definitions | Audio | IPA | Verb forms |
|----------|--------|-------------|-------|-----|------------|
| 🇬🇧 English | Oxford Learner's Dictionaries | ✓ | ✓ mp3 | ✓ | ✓ |
| 🇩🇪 German | DWDS | ✓ native | ✓ mp3 | most words | ✓ irregular |
| 🇷🇺 Russian | ru.Wiktionary | ✓ native | ✓ ogg+mp3 | ✓ | — |
| 🇫🇷 French | Larousse | ✓ native | ✓ mp3 | — | — |
| 🇦🇿 Azerbaijani | AZLEKS | ✓ native | — | bracketed | — |

No API key required. All sources are scraped directly.

---

## Usage

1. Open **Add Cards**
2. Type a word in the Word field
3. Click the **MultiDefine** button or press `Ctrl+Alt+Shift+D`
4. Choose a language from the popup (or press `1`–`5`)

The add-on fills:
- **DefinitionAndExamples** — definitions + examples with the headword clozed as `#word#`
- **Audio** — `[sound:…]` tag
- **Phonetics** — IPA transcription
- **VerbForms** — conjugated/inflected forms
- Opens a Google image search for the word

**Bulk define:** Browser → select notes → Edit → *MultiDefine in bulk…*

---

## Configuration

**Tools → Add-ons → MultiDefine → Config**

Key options:

| Option | Description |
|--------|-------------|
| `4. languages` | Ordered list of enabled languages — controls popup order and `1`–`N` keybinds |
| `enabled: false` | Hide a language without removing it |
| `max_examples` / `max_definitions` | Limits per sense (`false` = unlimited) |
| `corpus` | English only: `"American"`, `"British"`, `"American_first"`, `"British_first"` |

See [`AutoDefineAddon/config.md`](AutoDefineAddon/config.md) for full documentation.

---

## For developers

### Setup

```bash
git clone https://github.com/thegeneralist01/anki-multidefine.git
cd anki-multidefine

# Symlink into Anki (macOS/Linux)
ln -s "$PWD/AutoDefineAddon" \
  ~/Library/Application\ Support/Anki2/addons21/multidefine
```

Restart Anki. Edits to the repo are live immediately on next restart.

### Running tests

```bash
pip install requests beautifulsoup4
python3 scripts/check_providers.py
```

All 6/6 checks must pass.

### Building the package

```bash
bash scripts/build_ankiaddon.sh
# → multidefine.ankiaddon
```

### Adding a new language

1. Write `AutoDefineAddon/providers/<lang>.py` — subclass `DictionaryProvider`
2. Register in `AutoDefineAddon/providers/__init__.py`
3. Add entry to `4. languages` in `config.json`

See [AGENTS.md](AGENTS.md) for the full technical reference and [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

## License

GPL v2 — see individual files for attribution.
`oxford.py` is BSD 3-Clause © NearHuscarl.

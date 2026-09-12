# Contributing to MultiDefine

Thanks for your interest in contributing.

---

## Development setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/thegeneralist01/anki-multidefine.git
   cd anki-multidefine
   ```

2. **Symlink into Anki**
   ```bash
   ln -s "$PWD/AutoDefineAddon" \
     ~/Library/Application\ Support/Anki2/addons21/multidefine
   # Windows: mklink /D "%APPDATA%\Anki2\addons21\multidefine" "%CD%\AutoDefineAddon"
   ```

3. **Install test dependencies** (Python 3.9+, no Anki needed)
   ```bash
   pip install requests beautifulsoup4
   ```

4. **Restart Anki** to load the add-on. Any subsequent code change takes
   effect after restarting Anki again (or toggling the add-on off/on).

---

## Running the smoke tests

```bash
python3 scripts/check_providers.py
```

This hits each dictionary source live and checks that the provider returns
at least one sense with a description. **All 6/6 checks must pass** before
opening a PR. The script requires network access.

---

## Project structure

```
AutoDefineAddon/providers/   ← one file per language
autodefine.py                ← Anki integration only; no scraping here
scripts/check_providers.py   ← standalone test
scripts/build_ankiaddon.sh   ← builds the .ankiaddon package
```

See [AGENTS.md](AGENTS.md) for the full technical reference including the
`word_info` contract, import rules, and known gotchas.

---

## Adding a new language

1. Create `AutoDefineAddon/providers/<lang>.py`:
   - Subclass `DictionaryProvider`
   - Implement `get_words_info(word) -> list[dict]`
   - Return the standard `word_info` structure (see `AGENTS.md`)
   - Use `net.http_get` and `net.soup` for HTTP — never import `anki`/`aqt`
   - Do **not** use `.select()` or `.select_one()` (no CSS selectors)

2. Register it in `providers/__init__.py`

3. Add a config entry in `config.json` under `4. languages`

4. Add a test case in `scripts/check_providers.py`

5. Open a PR — include the `check_providers.py` output in the description

---

## Fixing a broken provider

Dictionary websites change their HTML without notice. If a provider starts
returning `[]` for words that should be found:

1. Run `scripts/check_providers.py` to confirm the failure
2. Fetch the live page and inspect the updated HTML structure
3. Update the relevant selectors in the provider file
4. Re-run the smoke test to confirm the fix
5. Open a PR

---

## Building the package

```bash
bash scripts/build_ankiaddon.sh
# → multidefine.ankiaddon
```

The `.ankiaddon` file is a zip of `AutoDefineAddon/` contents. It is
excluded from the repository and distributed via GitHub Releases.

---

## Pull request guidelines

- One logical change per PR
- All 6/6 smoke tests passing
- No `anki`/`aqt` imports in provider files
- No `.select()` / `.select_one()` calls (use `.find()` / `.find_all()`)
- If you add a new external HTTP source, verify it works with a
  descriptive User-Agent (see `AGENTS.md` → Wikimedia note)

---

## Reporting issues

Open an issue at https://github.com/thegeneralist01/anki-multidefine/issues
and include:

- Anki version (Help → About)
- The word you tried to define
- The language
- Any error message shown (or the tag added to the note)

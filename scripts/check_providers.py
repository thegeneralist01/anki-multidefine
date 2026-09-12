#!/usr/bin/env python3
"""
MultiDefine standalone provider smoke-test.

Usage (from repo root):
    python3 scripts/check_providers.py

Requires network access and the `requests` package.
bs4 and nltk are loaded from AutoDefineAddon/ (vendored).
No Anki installation needed.
"""

import importlib
import importlib.util
import pathlib
import sys
import types

# ---------------------------------------------------------------------------
# Bootstrap: put vendored libs on path, stub out anki/aqt before any imports.
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).parent.parent
ADDON_ROOT = REPO_ROOT / 'AutoDefineAddon'

# Vendored deps live in AutoDefineAddon/
sys.path.insert(0, str(ADDON_ROOT))

# Stub anki/aqt so any accidental import (e.g. from autodefine) fails loudly
# rather than crashing at attribute access.
for _name in ('anki', 'aqt', 'anki.hooks', 'aqt.utils', 'aqt.qt'):
    if _name not in sys.modules:
        stub = types.ModuleType(_name)
        stub.__path__ = []
        sys.modules[_name] = stub

# ---------------------------------------------------------------------------
# Register AutoDefineAddon as a package stub so relative imports in providers/
# resolve correctly without running AutoDefineAddon/__init__.py (which imports
# autodefine.py which imports anki/aqt).
# ---------------------------------------------------------------------------
addon_pkg = types.ModuleType('AutoDefineAddon')
addon_pkg.__path__ = [str(ADDON_ROOT)]
addon_pkg.__package__ = 'AutoDefineAddon'
addon_pkg.__spec__ = importlib.util.spec_from_file_location(
    'AutoDefineAddon',
    str(ADDON_ROOT / '__init__.py'),
    submodule_search_locations=[str(ADDON_ROOT)],
)
sys.modules['AutoDefineAddon'] = addon_pkg


def _load_provider(rel: str):
    """Import AutoDefineAddon.providers.<rel> and return the module."""
    full_name = f'AutoDefineAddon.providers.{rel}'
    if full_name in sys.modules:
        return sys.modules[full_name]

    file_path = ADDON_ROOT / 'providers' / f'{rel}.py'
    spec = importlib.util.spec_from_file_location(full_name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'AutoDefineAddon.providers'
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _bootstrap_providers():
    """Load providers package and all sub-modules in dependency order."""
    # Register AutoDefineAddon.providers package
    providers_dir = ADDON_ROOT / 'providers'
    pkg_name = 'AutoDefineAddon.providers'
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(providers_dir)]
        pkg.__package__ = pkg_name
        sys.modules[pkg_name] = pkg

    # Load in dependency order
    for mod_name in ('net', 'base', 'english_oxford', 'german_dwds',
                     'russian_wiktionary', 'french_larousse', 'azerbaijani_azleks'):
        _load_provider(mod_name)


_bootstrap_providers()


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def section(title: str):
    print()
    print('=' * 60)
    print(f'  {title}')
    print('=' * 60)


def check(provider, word: str, expect: dict) -> bool:
    print(f'\n[{provider.display_name}] "{word}"')
    try:
        results = provider.get_words_info(word)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f'  ERROR: {exc}')
        return False

    if not results:
        print('  FAIL: returned []')
        return False

    wi = results[0]
    name = wi.get('name', '')
    wordform = wi.get('wordform')
    prons = wi.get('pronunciations', [])
    ipa = prons[0].get('ipa') if prons else None
    mp3 = prons[0].get('mp3') if prons else None
    ogg = prons[0].get('ogg') if prons else None
    defs = wi.get('definitions', [])
    senses = defs[0].get('definitions', []) if defs else []
    n_senses = len(senses)
    examples = senses[0].get('examples', []) if senses else []
    first_ex = examples[0][:80] if examples else '(none)'
    verb_forms = wi.get('verb_forms_list', [])

    print(f'  name        : {name!r}')
    print(f'  wordform    : {wordform!r}')
    print(f'  #senses     : {n_senses}')
    print(f'  example[0]  : {first_ex!r}')
    print(f'  IPA         : {ipa!r}')
    print(f'  mp3         : {mp3!r}')
    print(f'  ogg         : {ogg!r}')
    print(f'  verb_forms  : {verb_forms}')

    ok = True
    min_senses = expect.get('min_senses', 1)
    if n_senses < min_senses:
        print(f'  FAIL: expected >= {min_senses} senses, got {n_senses}')
        ok = False
    if expect.get('has_audio') and not (mp3 or ogg):
        print('  FAIL: expected audio URL, got none')
        ok = False
    if expect.get('has_ipa') and not ipa:
        print('  FAIL: expected IPA, got none')
        ok = False
    if expect.get('verb_form_contains'):
        vfc = expect['verb_form_contains']
        if not any(vfc.lower() in vf.lower() for vf in verb_forms):
            print(f'  FAIL: expected verb form containing {vfc!r}, got {verb_forms}')
            ok = False
    if expect.get('example_contains'):
        ec = expect['example_contains'].lower()
        all_ex_text = ' '.join(
            ex for s in senses for ex in s.get('examples', [])
        ).lower()
        if ec not in all_ex_text:
            print(f'  FAIL: expected example containing {ec!r}')
            ok = False
    if expect.get('name_contains'):
        nc = expect['name_contains'].lower()
        if nc not in name.lower():
            print(f'  FAIL: expected name containing {nc!r}, got {name!r}')
            ok = False

    status = 'OK' if ok else 'FAIL'
    print(f'  {status}')
    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    from AutoDefineAddon.providers.english_oxford import OxfordEnglishProvider
    from AutoDefineAddon.providers.german_dwds import DWDSGermanProvider
    from AutoDefineAddon.providers.russian_wiktionary import WiktionaryRussianProvider
    from AutoDefineAddon.providers.french_larousse import LarousseFrencProvider
    from AutoDefineAddon.providers.azerbaijani_azleks import AzleksAzerbaijaniProvider

    results = []

    section('English — Oxford (regression)')
    en = OxfordEnglishProvider()
    en.set_corpus('American')
    results.append(check(en, 'content', {
        'min_senses': 1,
        'has_audio':  True,
        'has_ipa':    True,
    }))

    section('German — DWDS')
    de = DWDSGermanProvider()
    results.append(check(de, 'Haus', {
        'min_senses':       1,
        'has_audio':        True,
        'example_contains': 'haus',
    }))
    results.append(check(de, 'gehen', {
        'min_senses':         1,
        'verb_form_contains': 'gegangen',
    }))

    section('Russian — ru.Wiktionary')
    ru = WiktionaryRussianProvider()
    results.append(check(ru, 'дом', {
        'min_senses':       3,
        'example_contains': 'дом',
    }))

    section('French — Larousse')
    fr = LarousseFrencProvider()
    results.append(check(fr, 'maison', {
        'min_senses': 1,
    }))

    section('Azerbaijani — AZLEKS')
    az = AzleksAzerbaijaniProvider()
    results.append(check(az, 'ev', {
        'min_senses': 1,
    }))

    print()
    passed = sum(results)
    total = len(results)
    print(f'Results: {passed}/{total} passed')
    if passed < total:
        sys.exit(1)


if __name__ == '__main__':
    main()

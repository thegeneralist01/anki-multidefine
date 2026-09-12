# MultiDefine — Configuration

## `0. general`

| Key | Default | Description |
|-----|---------|-------------|
| `USE_DEFAULT_TEMPLATE` | `true` | Create/update a per-language note type automatically when defining a word in the editor. |
| `CLEAN_HTML_IN_SOURCE_FIELD` | `true` | Strip HTML from the source word field before lookup. |
| `REPLACE_BY` | `"#$#"` | Template used to cloak the headword in examples. `$` is replaced by the original token. The card template renders `#word#` as **word** on the back and as `____` in cloze mode. |

## `1. fields`

Zero-indexed field positions, shared across all languages.

| Key | Default | Field name in default note type |
|-----|---------|----------------------------------|
| `SOURCE_FIELD` | `0` | Word |
| `DEFINITION_FIELD` | `1` | DefinitionAndExamples |
| `AUDIO_FIELD` | `2` | Audio |
| `PHONETICS_FIELD` | `3` | Phonetics |
| `VERB_FORMS_FIELD` | `4` | VerbForms |
| `IMAGE_FIELD` | `5` | Image |

## `2. image`

| Key | Default | Description |
|-----|---------|-------------|
| `OPEN_IMAGES_IN_BROWSER` | `true` | Open a Google image search in the system browser after each define. |
| `SEARCH_APPEND` | `" AND (picture OR clipart OR illustration OR art)"` | Appended to the word when building the image search URL. |
| `OPEN_IMAGES_IN_BROWSER_LINK` | Google image search URL | `$` is replaced by `word + SEARCH_APPEND`. |

## `3. shortcuts`

| Key | Default |
|-----|---------|
| `PRIMARY_SHORTCUT` | `"ctrl+alt+shift+d"` |

Set to `""` to disable the keyboard shortcut.

## `4. languages`

An **ordered array** of language objects. The order determines both the display order in the
language-chooser popup and the `1`…`N` number keys.

### Language object fields

| Field | Required | Description |
|-------|----------|-------------|
| `key` | yes | Internal identifier. One of: `english`, `german`, `russian`, `french`, `azerbaijani`. |
| `enabled` | yes | Set to `false` to hide this language from the popup without removing it. |
| `display_name` | yes | Label shown in the popup button. |
| `note_type` | yes | Name of the Anki note type to create/switch to (when `USE_DEFAULT_TEMPLATE` is `true`). |
| `max_examples` | yes | Maximum examples per sense. Set to `false` for unlimited. |
| `max_definitions` | yes | Maximum senses shown per part-of-speech block. Set to `false` for unlimited. |
| `corpus` | English only | `"American"`, `"British"`, `"American_first"`, or `"British_first"`. Controls which pronunciation variant is preferred. |

### How to disable a language

Set `"enabled": false` for the language you want to hide:

```json
{ "key": "azerbaijani", "enabled": false, ... }
```

### How to reorder keybinds

Move entries up or down in the array. The first entry is key `1`, the second is key `2`, etc.

### How to point at a custom note type

Set `"note_type": "MyCustomNoteType"` for any language. The add-on will create or update
that note type with the standard fields (Word / DefinitionAndExamples / Audio / Phonetics /
VerbForms / Image) when `USE_DEFAULT_TEMPLATE` is `true`.

### Adding a new language (for developers)

1. Write `AutoDefineAddon/providers/<lang>.py` with a class extending `DictionaryProvider`.
2. Register it in `AutoDefineAddon/providers/__init__.py` under the new key.
3. Add an entry to `4. languages` in `config.json`.

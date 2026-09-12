# MultiDefine Anki Add-on
# Auto-defines words from multiple dictionaries (Oxford/English, DWDS/German,
# ru.Wiktionary/Russian, Larousse/French, AZLEKS/Azerbaijani).
#
# Copyright (c) Artem Petrov    apsapetrov@gmail.com
# https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries  Licensed under GPL v2
#
# Initially forked from
# Copyright (c) Robert Sanek    robertsanek.com    rsanek@gmail.com
# https://github.com/z1lc/AutoDefine                                     Licensed under GPL v2
#
# Then completely overwritten; multi-language layer added by thegeneralist.

import os
import pathlib
import re
import webbrowser
from urllib.parse import quote_plus
from typing import List, Optional, Tuple

from anki.hooks import addHook
from aqt import mw, gui_hooks
from aqt.addcards import AddCards
from aqt.editor import Editor
from aqt.qt import *
from aqt.utils import askUser, askUserDialog, tooltip
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

add_dialog: Optional[AddCards] = None

if getattr(mw.addonManager, 'getConfig', None):
    CONFIG = mw.addonManager.getConfig(__name__)
else:
    CONFIG = {}


def _cfg(section: str, key: str, default):
    section_data = CONFIG.get(section, {})
    if isinstance(section_data, dict):
        return section_data.get(key, default)
    return default


# Shared globals
TEST_MODE = _cfg('0. test mode', 'TEST_MODE', False)
USE_DEFAULT_TEMPLATE = _cfg('0. general', ' 1. USE_DEFAULT_TEMPLATE', True)
CLEAN_HTML_IN_SOURCE_FIELD = _cfg('0. general', ' 2. CLEAN_HTML_IN_SOURCE_FIELD', True)
REPLACE_BY = _cfg('0. general', ' 3. REPLACE_BY', '#$#')

SOURCE_FIELD = _cfg('1. fields', ' 1. SOURCE_FIELD', 0)
DEFINITION_FIELD = _cfg('1. fields', ' 2. DEFINITION_FIELD', 1)
AUDIO_FIELD = _cfg('1. fields', ' 3. AUDIO_FIELD', 2)
PHONETICS_FIELD = _cfg('1. fields', ' 4. PHONETICS_FIELD', 3)
VERB_FORMS_FIELD = _cfg('1. fields', ' 5. VERB_FORMS_FIELD', 4)
IMAGE_FIELD = _cfg('1. fields', ' 6. IMAGE_FIELD', 5)

OPEN_IMAGES_IN_BROWSER = _cfg('2. image', ' 1. OPEN_IMAGES_IN_BROWSER', True)
SEARCH_APPEND = _cfg('2. image', ' 2. SEARCH_APPEND',
                     ' AND (picture OR clipart OR illustration OR art)')
OPEN_IMAGES_IN_BROWSER_LINK = _cfg('2. image', ' 3. OPEN_IMAGES_IN_BROWSER_LINK',
                                   'https://www.google.com/search?q=$&tbm=isch&safe=off&tbs&hl=en&sa=X')

DEFAULT_SHORTCUT = 'ctrl+alt+shift+d'
_sc = _cfg('3. shortcuts', ' 1. PRIMARY_SHORTCUT', DEFAULT_SHORTCUT)
PRIMARY_SHORTCUT = (_sc.strip() if isinstance(_sc, str) else '') or DEFAULT_SHORTCUT

ERROR_TAG_NAME = 'MultiDefine_Error'
WORD_NOT_REPLACED_TAG_NAME = 'MultiDefine_WordNotReplaced'

SUPPORT_MESSAGE_TEXT = (
    'If you find MultiDefine useful, consider supporting the original '
    'AutoDefine Oxford project: https://ko-fi.com/artyompetrov'
)

# ---------------------------------------------------------------------------
# Language provider configuration
# ---------------------------------------------------------------------------

from .providers import build_provider


def _load_language_entries() -> List[dict]:
    """Build the ordered list of enabled language entries from config.

    Each entry dict: provider, display_name, note_type, max_examples,
                     max_definitions, key.
    """
    lang_list = CONFIG.get('4. languages', [])
    entries = []
    for lang_cfg in lang_list:
        if not lang_cfg.get('enabled', True):
            continue
        key = lang_cfg.get('key', '')
        provider = build_provider(key, lang_cfg)
        if provider is None:
            tooltip(f'MultiDefine: unknown language key "{key}" — skipped.', period=5000)
            continue
        entries.append({
            'provider':        provider,
            'key':             key,
            'display_name':    lang_cfg.get('display_name', provider.display_name),
            'note_type':       lang_cfg.get('note_type', f'MultiDefine_{provider.display_name}'),
            'max_examples':    lang_cfg.get('max_examples', 2),
            'max_definitions': lang_cfg.get('max_definitions', 3),
        })
    return entries


LANGUAGE_ENTRIES: List[dict] = _load_language_entries()

# ---------------------------------------------------------------------------
# Language chooser dialog
# ---------------------------------------------------------------------------


class LanguageChooserDialog(QDialog):
    """Small modal listing enabled languages; pick by click or number key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('MultiDefine — Choose Language')
        self.chosen_index: Optional[int] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Select a language:'))
        for i, entry in enumerate(LANGUAGE_ENTRIES, start=1):
            btn = QPushButton(f'{i}. {entry["display_name"]}')
            btn.clicked.connect(lambda _, idx=i - 1: self._select(idx))
            layout.addWidget(btn)
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        self.setLayout(layout)

    def _select(self, index: int):
        self.chosen_index = index
        self.accept()

    def keyPressEvent(self, event):
        key = event.key()
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            idx = key - Qt.Key.Key_1
            if idx < len(LANGUAGE_ENTRIES):
                self._select(idx)
                return
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)


def choose_language(parent=None) -> Optional[dict]:
    """Return an entry dict for the chosen language, or None if cancelled."""
    if not LANGUAGE_ENTRIES:
        tooltip('MultiDefine: no languages enabled in config.', period=5000)
        return None
    if len(LANGUAGE_ENTRIES) == 1:
        return LANGUAGE_ENTRIES[0]
    dlg = LanguageChooserDialog(parent)
    if dlg.exec() == QDialog.DialogCode.Accepted and dlg.chosen_index is not None:
        return LANGUAGE_ENTRIES[dlg.chosen_index]
    return None

# ---------------------------------------------------------------------------
# Sentence/word replacement
# ---------------------------------------------------------------------------


def _nltk_token_spans(txt: str, provider):
    tokens = provider.tokenize(txt)
    offset = 0
    for token in tokens:
        start = txt.index(token, offset)
        stop = start + len(token)
        yield token, start, stop
        offset = stop


def replace_word_in_sentence(
    words_to_replace_lists,
    sentence: str,
    highlight: bool,
    provider,
) -> Tuple[bool, str]:
    replaced_anything = False
    result = str()

    for words_to_replace in words_to_replace_lists:
        result = str()
        spans = list(_nltk_token_spans(sentence, provider))
        position = 0
        offset = 0

        while position < len(spans):
            all_match = True
            cur_position = position
            for word_to_replace in words_to_replace:
                if cur_position >= len(spans):
                    all_match = False
                    break
                token, start, stop = spans[cur_position]
                if provider.normalize(token.lower()) != word_to_replace:
                    all_match = False
                    break
                cur_position += 1

            if all_match:
                for i in range(len(words_to_replace)):
                    token, start, stop = spans[position + i]
                    replacement = REPLACE_BY.replace('$', token)
                    spaces_to_add = start - len(result) - offset
                    offset += len(token) - len(replacement)
                    if spaces_to_add < 0:
                        raise Exception('Incorrect spaces_to_add value')
                    result += ' ' * spaces_to_add
                    result += replacement
                position += len(words_to_replace)
                replaced_anything = True
            else:
                token, start, stop = spans[position]
                spaces_to_add = start - len(result) - offset
                if spaces_to_add < 0:
                    raise Exception('Incorrect spaces_to_add value')
                result += ' ' * spaces_to_add
                result += token
                position += 1

        sentence = result

    return replaced_anything, result

# ---------------------------------------------------------------------------
# Definition HTML
# ---------------------------------------------------------------------------


def get_definition_html(
    words_info: List[dict],
    verb_forms_list: List[str],
    provider,
    max_examples,
    max_definitions,
) -> Tuple[str, bool]:
    strings = []
    need_word_not_replaced_tag = False

    for word_info in words_info:
        definitions_by_namespaces = word_info.get('definitions', [])
        definitions = []
        for group in definitions_by_namespaces:
            for defn in group.get('definitions', []):
                definitions.append(defn)

        if not definitions:
            continue

        word = word_info['name']
        wordform = word_info.get('wordform')
        if wordform:
            strings.append('<i>' + wordform + '</i>')

        if max_definitions is not False:
            definitions = definitions[:max_definitions]

        words_to_replace = [word] + list(verb_forms_list)
        words_to_replace_lists = set(
            tuple(provider.normalize(t.lower()) for t in provider.tokenize(w))
            for w in words_to_replace
        )

        previous_definition_without_examples = False
        for definition in definitions:
            maybe_description = definition.get('description')
            if maybe_description is not None:
                (_, description) = replace_word_in_sentence(
                    words_to_replace_lists, maybe_description, False, provider)
                if previous_definition_without_examples:
                    strings.append('<br/>')
                strings.append('<div><b>' + description + '</b></div>')

            examples = definition.get('examples', []) + definition.get('extra_example', [])
            if max_examples is not False:
                examples = examples[:max_examples]

            if examples:
                strings.append('<ul>')
                for example in examples:
                    example = example.replace('/', ' / ')
                    (replaced_anything, example_clean) = replace_word_in_sentence(
                        words_to_replace_lists, example, True, provider)
                    need_word_not_replaced_tag |= not replaced_anything
                    strings.append('<li>' + example_clean + '</li>')
                strings.append('</ul>')
                previous_definition_without_examples = False
            else:
                previous_definition_without_examples = True

        strings.append('<hr/>')

    if strings:
        del strings[-1]

    return BeautifulSoup(''.join(strings), 'html.parser').prettify(), need_word_not_replaced_tag

# ---------------------------------------------------------------------------
# Phonetics
# ---------------------------------------------------------------------------


def get_phonetics(words_info: List[dict], provider) -> str:
    phonetics_dict: dict = {}
    prefixes = provider.pronunciation_prefixes
    for word_info in words_info:
        wordform = word_info.get('wordform') or 'none'
        pronunciations = word_info.get('pronunciations', [])
        _fill_phonetics_dict_prioritized(phonetics_dict, pronunciations, wordform, prefixes)

    if not phonetics_dict:
        return '<span class="do_not_show">No phonetics found</span>'
    elif len(phonetics_dict) == 1:
        return '[' + next(iter(phonetics_dict)) + ']'
    else:
        return '<br/>'.join(
            '[' + key + '] - ' + ', '.join(phonetics_dict[key])
            for key in phonetics_dict
        )


def _fill_phonetics_dict_prioritized(phonetics_dict, pronunciations, wordform, prefixes):
    for prefix in prefixes:
        for p in pronunciations:
            if p.get('prefix') == prefix:
                ipa = p.get('ipa')
                if ipa is None:
                    continue
                phonetics = ipa.replace('/', '').strip('[]').strip()
                if phonetics in phonetics_dict:
                    phonetics_dict[phonetics].append(wordform)
                else:
                    phonetics_dict[phonetics] = [wordform]

# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


def get_audio(words_info: List[dict], provider) -> str:
    audio_dict: dict = {}
    prefixes = provider.pronunciation_prefixes
    for word_info in words_info:
        wordform = word_info.get('wordform') or 'none'
        pronunciations = word_info.get('pronunciations', [])
        _fill_audio_dict_prioritized(audio_dict, pronunciations, wordform, prefixes)

    if not audio_dict:
        return '<span class="do_not_show">No audio found</span>'
    elif len(audio_dict) == 1:
        return f'[sound:{audio_dict[next(iter(audio_dict))]["audio_name"]}]'
    else:
        return '<br/>'.join(
            f'[sound:{audio_dict[k]["audio_name"]}] - ' + ', '.join(audio_dict[k]['wordform'])
            for k in audio_dict
        )


def _fill_audio_dict_prioritized(audio_dict, pronunciations, wordform, prefixes):
    from .providers import net as _net

    for prefix in prefixes:
        for p in pronunciations:
            if p.get('prefix') != prefix:
                continue
            # Pick mp3 over ogg
            audio_url = p.get('mp3') or p.get('ogg')
            if not audio_url:
                continue

            # Determine filename
            explicit_name = p.get('audio_name')
            if explicit_name:
                audio_name = explicit_name
            else:
                from urllib.parse import unquote
                audio_name = unquote(audio_url.split('/')[-1].split('?')[0])
                # Ensure extension
                if not any(audio_name.lower().endswith(ext) for ext in ('.mp3', '.ogg', '.wav')):
                    audio_name += '.mp3'

            if audio_name in audio_dict:
                audio_dict[audio_name]['wordform'].append(wordform)
            else:
                collection_path = pathlib.Path(mw.col.path).parent.absolute()
                media_path = os.path.join(str(collection_path), 'collection.media')
                audio_path = os.path.join(media_path, audio_name)
                if not os.path.exists(audio_path):
                    data = _net.fetch_bytes(audio_url)
                    with open(audio_path, 'wb') as f:
                        f.write(data)
                audio_dict[audio_name] = {'wordform': [wordform], 'audio_name': audio_name}
            return  # first matching prefix/format wins

# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------


def insert_into_field(note, text: str, field_id: int, overwrite: bool = False):
    if len(note.fields) <= field_id:
        raise MultiDefineError(
            "MultiDefine: Tried to insert '%s' into user-configured field number %d "
            "(0-indexed), but note type only has %d fields. Use a different note type "
            'with %d or more fields, or change the index in the Add-on configuration.'
            % (text, field_id, len(note.fields), field_id + 1)
        )
    if overwrite:
        note.fields[field_id] = text
    else:
        note.fields[field_id] += text


def clean_html(raw_html: str) -> str:
    return re.sub(re.compile('<.*?>'), '', raw_html).replace('&nbsp;', ' ')


def get_word(note) -> str:
    word = note.fields[SOURCE_FIELD]
    if CLEAN_HTML_IN_SOURCE_FIELD:
        word = clean_html(word)
    return word.strip()

# ---------------------------------------------------------------------------
# Note-type management
# ---------------------------------------------------------------------------


def new_add_cards(addcards: AddCards):
    global add_dialog
    add_dialog = addcards


def switch_model(name: str):
    try:
        notetype = mw.col.models.by_name(name)
        if notetype:
            add_dialog.notetype_chooser.selected_notetype_id = notetype['id']
        else:
            tooltip('No note type with name: ' + name)
    except Exception:
        pass


def addCustomModel(col, name: str):
    mm = col.models
    model = mm.byName(name)

    new_model = False
    if not model:
        model = mm.new(name)
        new_model = True

    model['flds'] = [
        {'name': 'Word',                 'ord': SOURCE_FIELD,      'sticky': False, 'rtl': False,
         'font': 'Arial', 'size': 20,
         'description': 'Write a word to define here',
         'plainText': False, 'collapsed': False, 'excludeFromSearch': False},
        {'name': 'DefinitionAndExamples','ord': DEFINITION_FIELD,  'sticky': False, 'rtl': False,
         'font': 'Arial', 'size': 20,
         'description': 'Leave empty, will be filled automatically',
         'plainText': False, 'collapsed': False, 'excludeFromSearch': False},
        {'name': 'Audio',                'ord': AUDIO_FIELD,       'sticky': False, 'rtl': False,
         'font': 'Arial', 'size': 20,
         'description': 'Leave empty, will be filled automatically',
         'plainText': False, 'collapsed': False, 'excludeFromSearch': False},
        {'name': 'Phonetics',            'ord': PHONETICS_FIELD,   'sticky': False, 'rtl': False,
         'font': 'Arial', 'size': 20,
         'description': 'Leave empty, will be filled automatically',
         'plainText': False, 'collapsed': False, 'excludeFromSearch': False},
        {'name': 'VerbForms',            'ord': VERB_FORMS_FIELD,  'sticky': False, 'rtl': False,
         'font': 'Arial', 'size': 20,
         'description': 'Leave empty, will be filled automatically',
         'plainText': False, 'collapsed': False, 'excludeFromSearch': False},
        {'name': 'Image',                'ord': IMAGE_FIELD,       'sticky': False, 'rtl': False,
         'font': 'Arial', 'size': 20,
         'description': 'Insert an image here',
         'plainText': False, 'collapsed': False, 'excludeFromSearch': False},
    ]

    model['css'] = """
.card {
  font-family: arial;
  font-size: 20px;
  color: black;
  background-color: white;
  text-align: left;
}

.front {
  text-align: center;
}

.do_not_show {
  display: none;
}

.img {
  text-align: center;
}

img {
  padding-left: 5px;
  padding-right: 5px;
}

b {
  color: black;
}

i {
  color: grey;
}

.nightMode b {
  color: #8ab4f8;
}

.nightMode i {
  color: silver;
}

.nightMode a {
  color: #8ab4f8;
}
"""

    t = _get_template(mm, model, 'Normal')
    t['qfmt'] = (
        '<div class="front">{{Word}} {{Audio}} <br/> {{Phonetics}} <br/> {{VerbForms}}</div>'
    )
    t['afmt'] = """
<div class="front">{{Word}} {{Audio}} <br/> {{Phonetics}} <br/> {{VerbForms}}</div>
<hr id="answer">
<div class="img" id="img_div">{{Image}}</div>
<hr id="image_hr">
<div id="to_replace">
{{DefinitionAndExamples}}
</div>
<script>
    document.getElementById('to_replace').innerHTML =
    document.getElementById('to_replace').innerHTML.replace(/[#]([^#]+)[#]/ig, "<b>$1</b>");

    if (document.getElementById('img_div').innerHTML.toString().length == 0)
    {
        document.getElementById('image_hr').style.display = 'none';
    }
</script>
"""

    t = _get_template(mm, model, 'Reverse')
    t['qfmt'] = """
<script>
    var hintString = '{{Word}}';
    var position = 0;
    function hint() {
    position += 1;
    if (hintString.length <= position)
    {
        document.getElementById('hint_link').style.display='none'
        document.getElementById('verb_forms').style.display='inline';
        for (let el of document.querySelectorAll('.word')) el.style.display = 'inline';
        for (let el of document.querySelectorAll('.replacement')) el.style.display = 'none';
    }
    return hintString.substring(0, position);
    }
</script>

<div class="front">
    {{type:Word}}
    <br id="hint_br">
    <a id="hint_link" class=hint href="#"onclick="document.getElementById('hint_div').style.display='inline-block';document.getElementById('hint_div').innerHTML=hint();return false;">Show hint</a>
    <div id="hint_div" class=hint style="display: none"></div>
    <br>
    <span id="phonetics" style="display: none"> {{Phonetics}}</span>
    <br>
    <span id="verb_forms" style="display: none"> {{VerbForms}}</span>
</div>

<hr id="answer">
<div class="img" id="img_div">{{Image}}</div>
<hr id="image_hr">
<div id="to_replace">
{{DefinitionAndExamples}}
</div>

<script>
    document.getElementById('to_replace').innerHTML =
     document.getElementById('to_replace').innerHTML
     .replace(/[#]([^#]+)[#]/ig, "<span class='word'><b>$1</b></span><span class='replacement'>____</span>");

    for (let el of document.querySelectorAll('.word')) el.style.display = 'none';
    for (let el of document.querySelectorAll('.replacement')) el.style.display = 'inline';

    if (document.getElementById('img_div').innerHTML.toString().length == 0)
    {
        document.getElementById('image_hr').style.display = 'none';
    }
</script>
"""
    t['afmt'] = """
<div class="front">{{Audio}}</div>
    {{FrontSide}}
<script>
    document.getElementById('hint_link').style.display='none';
    document.getElementById('phonetics').style.display='inline';
    document.getElementById('verb_forms').style.display='inline';
    for (let el of document.querySelectorAll('.word')) el.style.display = 'inline';
    for (let el of document.querySelectorAll('.replacement')) el.style.display = 'none';
</script>
"""

    if new_model:
        mm.add(model)
    else:
        mm.update(model)


def _get_template(mm, model, template_name: str):
    for t in model['tmpls']:
        if t['name'] == template_name:
            return t
    t = mm.newTemplate(template_name)
    mm.addTemplate(model, t)
    return t

# ---------------------------------------------------------------------------
# Core define logic
# ---------------------------------------------------------------------------


def get_data(note, entry: dict, is_bulk: bool):
    """Fetch and fill fields for *note* using the provider in *entry*."""
    provider = entry['provider']
    max_examples = entry['max_examples']
    max_definitions = entry['max_definitions']

    try:
        word = get_word(note)
        if not word:
            raise MultiDefineError('There is no word in SOURCE_FIELD')

        if CLEAN_HTML_IN_SOURCE_FIELD:
            insert_into_field(note, word, SOURCE_FIELD, overwrite=True)

        try:
            words_info = provider.get_words_info(word)
        except Exception as _e:
            raise MultiDefineError(
                f'[{provider.display_name}] {type(_e).__name__}: {str(_e)[:150]}'
            ) from _e

        if not words_info:
            raise MultiDefineError('Word not found in dictionary')

        found_word = words_info[0]['name']
        if found_word != word:
            if TEST_MODE or is_bulk:
                raise MultiDefineError(f"Found definition for word '{found_word}' instead")
            else:
                if askUser(f"Attention! found another word '{found_word}', replace source field?"):
                    insert_into_field(note, found_word, SOURCE_FIELD, overwrite=True)
                    word = found_word

        # Aggregate verb forms from all word_infos
        verb_forms_list: List[str] = []
        for wi in words_info:
            verb_forms_list.extend(wi.get('verb_forms_list', []))

        # Definition
        insert_into_field(note, '', DEFINITION_FIELD, overwrite=True)
        (definition_html, need_word_not_replaced_tag) = get_definition_html(
            words_info, verb_forms_list, provider, max_examples, max_definitions)
        insert_into_field(note, definition_html, DEFINITION_FIELD, overwrite=False)

        if need_word_not_replaced_tag:
            if WORD_NOT_REPLACED_TAG_NAME not in note.tags:
                note.tags.append(WORD_NOT_REPLACED_TAG_NAME)
        else:
            if WORD_NOT_REPLACED_TAG_NAME in note.tags:
                note.tags.remove(WORD_NOT_REPLACED_TAG_NAME)

        # Phonetics
        phonetics = get_phonetics(words_info, provider)
        insert_into_field(note, phonetics, PHONETICS_FIELD, overwrite=True)

        # Audio
        audio = get_audio(words_info, provider)
        insert_into_field(note, audio, AUDIO_FIELD, overwrite=True)

        # Verb forms field
        insert_into_field(note, ' '.join(verb_forms_list), VERB_FORMS_FIELD, overwrite=True)

        # Image search
        if OPEN_IMAGES_IN_BROWSER and not is_bulk:
            link = OPEN_IMAGES_IN_BROWSER_LINK.replace('$', quote_plus(word + SEARCH_APPEND))
            webbrowser.open(link, 0, False)

        if ERROR_TAG_NAME in note.tags:
            note.tags.remove(ERROR_TAG_NAME)

    except Exception as error:
        if ERROR_TAG_NAME not in note.tags:
            note.tags.append(ERROR_TAG_NAME)
        raise error

# ---------------------------------------------------------------------------
# Bulk define
# ---------------------------------------------------------------------------


def save_error(count: int, error_text: str, word, errors: list):
    if word:
        errors.append(f'{word}: {error_text}')
    else:
        errors.append(f'Word number {count}: {error_text}')


def bulkDefine(browser, entry: dict):
    ids = browser.selectedNotes()
    if not ids:
        tooltip('No cards selected.')
        return
    mw.checkpoint('MultiDefine')
    mw.progress.start(immediate=True, max=len(ids))
    browser.model.beginReset()
    errors = []

    def process(nids, mw):
        count = 0
        max_count = len(nids)
        for nid in nids:
            count += 1
            note = mw.col.getNote(nid)
            word = None
            try:
                word = get_word(note)
                mw.taskman.run_on_main(
                    lambda c=count, w=word, m=max_count:
                    mw.progress.update(value=c, label=w, process=False, max=m)
                )
                get_data(note, entry, is_bulk=True)
            except MultiDefineError as error:
                save_error(count, error.message, word, errors)
            except Exception:
                save_error(count, 'Exception', word, errors)
            note.flush()

    def onFinish(future):
        browser.model.endReset()
        mw.requireReset()
        mw.progress.finish()
        mw.reset()
        if errors:
            error_message = '<br/><br/>'.join(errors)
            askUserDialog(error_message, ['OK'],
                          title='Bulk operation finished with some errors',
                          parent=browser).run()

    mw.taskman.run_in_background(process, onFinish, args={'nids': ids, 'mw': mw})

# ---------------------------------------------------------------------------
# Editor integration
# ---------------------------------------------------------------------------


def flush_note(note):
    try:
        note.flush()
    except Exception:
        pass


def focus_zero_field(editor):
    if TEST_MODE:
        return
    editor.web.eval('focusField(%d);' % 0)


def get_data_with_exception_handling(editor: Editor, entry: dict) -> bool:
    """Run the define pipeline. Returns True on success, False if a user-visible error occurred."""
    try:
        if USE_DEFAULT_TEMPLATE:
            note_type_name = entry['note_type']
            addCustomModel(mw.col, note_type_name)
            switch_model(note_type_name)

        note = editor.note
        error_occurred = False
        try:
            get_data(note, entry, is_bulk=False)
        except MultiDefineError as error:
            tooltip(error.message, period=10000)
            error_occurred = True

        flush_note(note)
        mw.requireReset()
        mw.reset()
        editor.loadNote()
        focus_zero_field(editor)
        return not error_occurred
    except Exception as ex:
        raise Exception(
            '\n\nATTENTION! Please screenshot this error message and open an issue on \n'
            'https://github.com/thegeneralist01/anki-multidefine/issues \n'
            'so I could investigate the reason of the error and fix it'
        ) from ex


def run_autodefine(editor: Editor):
    entry = choose_language(editor.widget)
    if entry is None:
        return
    success = get_data_with_exception_handling(editor, entry)
    if success:
        tooltip(SUPPORT_MESSAGE_TEXT, period=5000)


def setup_buttons(buttons, editor):
    button_kwargs = dict(
        icon=os.path.join(os.path.dirname(__file__), 'images', 'icon30.png'),
        cmd='AD',
        func=lambda ed: ed.saveNow(lambda: run_autodefine(ed)),
        tip='MultiDefine Word (%s)' % ('no shortcut' if not PRIMARY_SHORTCUT else PRIMARY_SHORTCUT),
        toggleable=False,
        label='',
        disables=False,
    )
    if PRIMARY_SHORTCUT:
        button_kwargs['keys'] = PRIMARY_SHORTCUT
    buttons.append(editor.addButton(**button_kwargs))
    return buttons


def setupMenu(browser):
    menu = browser.form.menuEdit
    menu.addSeparator()
    a = menu.addAction('MultiDefine in bulk...')
    if PRIMARY_SHORTCUT:
        a.setShortcut(QKeySequence(PRIMARY_SHORTCUT))

    def _bulk_with_chooser(b=browser):
        entry = choose_language(b)
        if entry is not None:
            bulkDefine(b, entry)

    a.triggered.connect(lambda _, b=browser: _bulk_with_chooser(b))


addHook('browser.setupMenus', setupMenu)
addHook('setupEditorButtons', setup_buttons)
gui_hooks.add_cards_did_init.append(new_add_cards)


class MultiDefineError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

try:
    from . import autodefine
except Exception as ex:
    raise Exception("\n\nATTENTION! Please screenshot this error message and open an issue on \n"
                    "https://github.com/thegeneralist/anki-multi-language-auto-define/issues \n"
                    "so I could investigate the reason of the error and fix it") from ex
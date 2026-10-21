import traceback


def safe(fn):
    """Вызвать fn, проглатывая RuntimeError (C++-объект уже удалён) и печатая прочие ошибки."""
    try:
        return fn()
    except RuntimeError:
        return None
    except Exception:
        traceback.print_exc()
        return None

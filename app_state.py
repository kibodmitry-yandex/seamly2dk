import os
import json


def _default_app_state_path():
    # Prefer user-specific roaming app data on Windows, else use user home .local/share
    try:
        if os.name == 'nt':
            base = os.environ.get('APPDATA') or os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming')
            outdir = os.path.join(base, 'seamly2dk')
        else:
            outdir = os.path.join(os.path.expanduser('~'), '.local', 'share', 'seamly2dk')
        os.makedirs(outdir, exist_ok=True)
        return os.path.join(outdir, 'app_state.json')
    except Exception:
        # fallback to package dir
        return os.path.join(os.path.dirname(__file__), 'app_state.json')

APP_STATE_PATH = _default_app_state_path()


def load_state():
    try:
        if os.path.exists(APP_STATE_PATH):
            with open(APP_STATE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_state(state: dict):
    try:
        tmp = APP_STATE_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, APP_STATE_PATH)
    except Exception:
        pass

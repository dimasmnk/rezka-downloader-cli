from pathlib import Path
import json
import os
from typing import Optional, Dict, Any


def choose_preferred_quality(videos_keys):
    # hardcoded exact labels (user-specified). We check in reverse to prefer higher qualities.
    preferred = ['4K', '2K', '1080p Ultra', '1080p', '720p', '480p', '360p']
    for q in preferred:
        if q in videos_keys:
            return q
    return None


def _get_session_dir() -> Path:
    """Return the directory path where the session file will be stored.

    Per user request, sessions are saved under the user's home folder in a
    folder named `rezka-downloader-cli`.
    """
    return Path.home() / 'rezka-downloader-cli'


def get_session_file() -> Path:
    """Return the full path to the session file."""
    return _get_session_dir() / 'session.json'


def save_session(cookies: Dict[str, Any]) -> Path:
    """Persist cookies to the session file and return the file path.

    File is written as JSON with owner read/write permissions (0o600).
    """
    session_dir = _get_session_dir()
    session_dir.mkdir(parents=True, exist_ok=True)
    path = get_session_file()
    data = {'cookies': cookies}
    # write atomically
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    # set restrictive permissions before moving into place
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        # best effort; ignore if not supported on platform
        pass
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    return path


def load_session() -> Optional[Dict[str, Any]]:
    """Load session file and return cookies dict or None if unavailable."""
    path = get_session_file()
    if not path.exists():
        return None
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get('cookies')
    except Exception:
        return None
    return None
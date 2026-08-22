import ctypes
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

from .scraper import HEADERS, TIMEOUT

_linux_players = [
    ["mpg123", "-q"],
    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
    ["cvlc", "--play-and-exit", "-q"],
]


def _play_windows(path: Path) -> bool:
    try:
        mci = ctypes.windll.winmm  # type: ignore[attr-defined]
    except AttributeError:
        return False
    alias = f"dictcli_audio_{int(time.time() * 1000)}"
    cmd = f'open "{path}" type mpegvideo alias {alias}'
    if mci.mciSendStringW(cmd, None, 0, None) != 0:
        return False
    try:
        mci.mciSendStringW(f"play {alias} wait", None, 0, None)
    finally:
        mci.mciSendStringW(f"close {alias}", None, 0, None)
    return True


def _play_macos(path: Path) -> bool:
    if shutil.which("afplay"):
        return subprocess.run(["afplay", str(path)]).returncode == 0
    return False


def _play_linux(path: Path) -> bool:
    for player in _linux_players:
        if shutil.which(player[0]):
            return subprocess.run([*player, str(path)]).returncode == 0
    return False


def play_url(url: str) -> tuple[bool, str]:
    """Download and play an audio clip. Returns (success, message)."""
    tmp_path = None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(resp.content)
            tmp_path = Path(f.name)

        if sys.platform == "win32":
            ok = _play_windows(tmp_path)
        elif sys.platform == "darwin":
            ok = _play_macos(tmp_path)
        else:
            ok = _play_linux(tmp_path)

        if not ok:
            return False, "no audio player available on this system"
        return True, ""
    except requests.RequestException as exc:
        return False, f"could not download audio ({exc.__class__.__name__})"
    except Exception as exc:
        return False, f"playback failed ({exc.__class__.__name__})"
    finally:
        if tmp_path is not None:
            try:
                time.sleep(0.05)
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

from __future__ import annotations

import base64
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

from tts_local import preheat as local_preheat
from tts_local import speak as local_speak
from tts_local import speak_many as local_speak_many


def _tts_mode() -> str:
    return (os.environ.get("CLAWEASE_TTS_MODE") or "local").strip().lower()


def _volcengine_required_env() -> dict[str, str]:
    keys = {
        "appid": "VOLCENGINE_TTS_APPID",
        "token": "VOLCENGINE_TTS_TOKEN",
        "cluster": "VOLCENGINE_TTS_CLUSTER",
        "voice_type": "VOLCENGINE_TTS_VOICE_TYPE",
    }
    values: dict[str, str] = {}
    for field, env_name in keys.items():
        value = (os.environ.get(env_name) or "").strip()
        if not value:
            raise RuntimeError(f"missing env for volcengine TTS: {env_name}")
        values[field] = value
    return values


def _volcengine_payload(text: str) -> bytes:
    conf = _volcengine_required_env()
    body = {
        "app": {
            "appid": conf["appid"],
            "token": conf["token"],
            "cluster": conf["cluster"],
        },
        "user": {"uid": os.environ.get("VOLCENGINE_TTS_UID", "clawease-elder")},
        "audio": {
            "voice_type": conf["voice_type"],
            "encoding": "wav",
            "rate": int(os.environ.get("VOLCENGINE_TTS_RATE", "24000")),
            "speed_ratio": float(os.environ.get("VOLCENGINE_TTS_SPEED", "0.95")),
            "volume_ratio": float(os.environ.get("VOLCENGINE_TTS_VOLUME", "1.0")),
            "pitch_ratio": float(os.environ.get("VOLCENGINE_TTS_PITCH", "1.0")),
            "emotion": os.environ.get("VOLCENGINE_TTS_EMOTION", "happy"),
            "language": os.environ.get("VOLCENGINE_TTS_LANGUAGE", "cn"),
        },
        "request": {
            "reqid": str(uuid4()),
            "text": text,
            "text_type": "plain",
            "operation": "query",
        },
    }
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


def _play_volcengine_wav(data: bytes, blocking: bool = True) -> None:
    import winsound

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(data)
        wav_path = Path(tmp.name)
    flags = winsound.SND_FILENAME
    if not blocking:
        flags |= winsound.SND_ASYNC
    try:
        winsound.PlaySound(str(wav_path), flags)
    finally:
        if blocking:
            wav_path.unlink(missing_ok=True)


def _volcengine_speak(text: str, blocking: bool = True) -> None:
    payload = _volcengine_payload(text)
    token = (os.environ.get("VOLCENGINE_TTS_TOKEN") or "").strip()
    req = urllib.request.Request(
        "https://openspeech.bytedance.com/api/v1/tts",
        data=payload,
        headers={
            "Authorization": f"Bearer;{token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Volcengine TTS HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Volcengine TTS request failed: {exc}") from exc

    if int(result.get("code", 0)) != 3000 or not result.get("data"):
        raise RuntimeError(f"Volcengine TTS failed: {result!r}")
    _play_volcengine_wav(base64.b64decode(result["data"]), blocking=blocking)


def preheat() -> str:
    mode = _tts_mode()
    if mode == "local":
        return local_preheat()
    if mode == "volcengine":
        _volcengine_required_env()
        return "volcengine"
    raise RuntimeError(f"unsupported CLAWEASE_TTS_MODE: {mode}")


def speak(text: str, blocking: bool = True) -> None:
    if not text:
        return
    mode = _tts_mode()
    if mode == "local":
        local_speak(text, blocking=blocking)
        return
    if mode == "volcengine":
        _volcengine_speak(text, blocking=blocking)
        return
    raise RuntimeError(f"unsupported CLAWEASE_TTS_MODE: {mode}")


def speak_many(texts: list[str], pause_sec: float = 0.3) -> None:
    mode = _tts_mode()
    if mode == "local":
        local_speak_many(texts, pause_sec=pause_sec)
        return
    for text in texts:
        speak(text, blocking=True)

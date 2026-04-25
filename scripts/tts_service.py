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
    values: dict[str, str] = {}
    voice_type = (os.environ.get("VOLCENGINE_TTS_VOICE_TYPE") or "").strip()
    if not voice_type:
        raise RuntimeError("missing env for volcengine TTS: VOLCENGINE_TTS_VOICE_TYPE")
    values["voice_type"] = voice_type

    api_key = (os.environ.get("VOLCENGINE_TTS_API_KEY") or "").strip()
    if api_key:
        values["api_version"] = "v3"
        values["api_key"] = api_key
        values["resource_id"] = (
            os.environ.get("VOLCENGINE_TTS_RESOURCE_ID") or "volc.service_type.10029"
        ).strip()
        values["endpoint"] = (
            os.environ.get("VOLCENGINE_TTS_ENDPOINT")
            or "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
        ).strip()
        values["appid"] = (os.environ.get("VOLCENGINE_TTS_APPID") or "clawease").strip()
        return values

    values["api_version"] = "v1"
    values["appid"] = (os.environ.get("VOLCENGINE_TTS_APPID") or "").strip()
    values["token"] = (os.environ.get("VOLCENGINE_TTS_TOKEN") or "").strip()
    values["cluster"] = (os.environ.get("VOLCENGINE_TTS_CLUSTER") or "").strip()
    values["endpoint"] = (
        os.environ.get("VOLCENGINE_TTS_ENDPOINT")
        or "https://openspeech.bytedance.com/api/v1/tts"
    ).strip()
    missing = [name for name in ("appid", "token", "cluster") if not values[name]]
    if missing:
        env_names = {
            "appid": "VOLCENGINE_TTS_APPID",
            "token": "VOLCENGINE_TTS_TOKEN",
            "cluster": "VOLCENGINE_TTS_CLUSTER",
        }
        raise RuntimeError(
            "missing env for volcengine TTS: "
            + ", ".join(env_names[item] for item in missing)
        )
    return values


def _volcengine_payload(text: str, conf: dict[str, str]) -> bytes:
    default_op = "query" if conf["api_version"] == "v1" else "submit"
    body = {
        "app": {"appid": conf["appid"]},
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
            "operation": os.environ.get("VOLCENGINE_TTS_OPERATION", default_op),
        },
    }
    if conf["api_version"] == "v1":
        body["app"]["token"] = conf["token"]
        body["app"]["cluster"] = conf["cluster"]
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
    conf = _volcengine_required_env()
    payload = _volcengine_payload(text, conf)
    headers = {"Content-Type": "application/json"}
    if conf["api_version"] == "v3":
        headers["X-Api-Key"] = conf["api_key"]
        headers["X-Api-Resource-Id"] = conf["resource_id"]
    else:
        headers["Authorization"] = f"Bearer;{conf['token']}"

    req = urllib.request.Request(conf["endpoint"], data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
            content_type = (resp.headers.get("Content-Type") or "").lower()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Volcengine TTS HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Volcengine TTS request failed: {exc}") from exc

    looks_like_json = (
        "application/json" in content_type
        or "text/plain" in content_type
        or raw.lstrip().startswith(b"{")
    )
    if looks_like_json:
        result = json.loads(raw.decode("utf-8", errors="replace"))
        code = int(result.get("code", 0))
        if conf["api_version"] == "v1":
            if code != 3000 or not result.get("data"):
                raise RuntimeError(f"Volcengine TTS failed: {result!r}")
            _play_volcengine_wav(base64.b64decode(result["data"]), blocking=blocking)
            return
        if code != 3000:
            hint = ""
            if code == 55000000:
                hint = (
                    " (resource_id and voice_type mismatch, "
                    "check VOLCENGINE_TTS_RESOURCE_ID and VOLCENGINE_TTS_VOICE_TYPE)"
                )
            raise RuntimeError(f"Volcengine TTS failed: {result!r}{hint}")
        data = result.get("data")
        if not data:
            raise RuntimeError(f"Volcengine TTS succeeded but no audio data: {result!r}")
        if isinstance(data, str):
            _play_volcengine_wav(base64.b64decode(data), blocking=blocking)
            return
        raise RuntimeError(f"Volcengine TTS returned unsupported data format: {result!r}")

    _play_volcengine_wav(raw, blocking=blocking)


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

"""本地 TTS 封装（Windows SAPI）。

首选 pyttsx3（跨 Python 版本好用），失败回退 win32com.Dispatch("SAPI.SpVoice")。
首次 Engine().init 大约 1-2s，`preheat()` 让 voice_to_action 启动时就吃掉这段延迟。
Layer 2 会替换成 OpenClaw 流式 TTS 或云端 TTS。
"""
from __future__ import annotations

import threading
from typing import Callable

_engine = None
_engine_kind = ""  # "pyttsx3" | "sapi" | ""
_lock = threading.Lock()


def _init_pyttsx3():
    import pyttsx3

    eng = pyttsx3.init()
    # 适当放慢（默认 200 wpm，老人听不清）
    try:
        eng.setProperty("rate", 175)
    except Exception:
        pass
    return eng


def _init_sapi():
    import win32com.client

    return win32com.client.Dispatch("SAPI.SpVoice")


def _get_engine():
    global _engine, _engine_kind
    if _engine is not None:
        return _engine, _engine_kind
    try:
        _engine = _init_pyttsx3()
        _engine_kind = "pyttsx3"
        return _engine, _engine_kind
    except Exception:
        pass
    try:
        _engine = _init_sapi()
        _engine_kind = "sapi"
        return _engine, _engine_kind
    except Exception as e:
        raise RuntimeError(
            f"TTS 初始化失败（pyttsx3 + SAPI 均不可用）：{e!r}\n"
            f"建议：pip install pyttsx3 pywin32"
        )


def preheat() -> str:
    """启动时预热，避免第一次 speak 延迟。返回已启用的引擎名。"""
    with _lock:
        _, kind = _get_engine()
    return kind


def speak(text: str, blocking: bool = True) -> None:
    """朗读一段文本。blocking=True 等播完返回。"""
    if not text:
        return
    with _lock:
        eng, kind = _get_engine()
        if kind == "pyttsx3":
            eng.say(text)
            if blocking:
                eng.runAndWait()
        else:  # sapi
            # SAPI: Speak(text, flags). flag 1 = async; 0 = sync.
            eng.Speak(text, 0 if blocking else 1)


def speak_many(texts: list[str], pause_sec: float = 0.3) -> None:
    """连续朗读多条（中间短暂停顿）。"""
    import time as _t

    for t in texts:
        speak(t, blocking=True)
        if pause_sec:
            _t.sleep(pause_sec)


if __name__ == "__main__":
    # smoke: python scripts/tts_local.py
    kind = preheat()
    print(f"[tts_local] engine={kind}")
    speak("你好，ClawEase 语音助手已就绪。", blocking=True)

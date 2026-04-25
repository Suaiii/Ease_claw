from __future__ import annotations

import argparse
import dataclasses
import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "demo"

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import voice_to_action as vta
from elder_summary import summarize_inbox_for_elder


RUN_LOCK = threading.Lock()


def _json_ready(value):
    if dataclasses.is_dataclass(value):
        return {key: _json_ready(val) for key, val in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def bootstrap_runtime() -> None:
    vta.load_env(vta.DEFAULT_ENV)
    vta.configure_runtime_env()
    vta.refresh_runtime_flags()
    vta.OPENCLAW_AVAILABLE = True


def load_contacts_summary() -> list[dict]:
    contacts = vta.load_contacts(vta.DEFAULT_CONTACTS)
    rows: list[dict] = []
    for name, entry in contacts.items():
        if not name or name.startswith("_"):
            continue
        phone = ""
        note = ""
        if isinstance(entry, dict):
            phone = str(entry.get("phone") or "").strip()
            note = str(entry.get("note") or "").strip()
        rows.append({"name": name, "phone": phone, "note": note})
    rows.sort(key=lambda item: item["name"])
    return rows


def probe_adb_devices() -> dict:
    bootstrap_runtime()
    adb_path = os.environ.get("ADBUTILS_ADB_PATH") or str(vta.DEFAULT_ADB)
    if not adb_path:
        return {"ok": False, "detail": "ADB is not configured", "devices": []}
    try:
        proc = subprocess.run(
            [adb_path, "devices"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            env=vta.current_subprocess_env(),
        )
    except Exception as exc:
        return {"ok": False, "detail": f"adb devices failed: {exc!r}", "devices": []}
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "adb devices failed"
        return {"ok": False, "detail": detail, "devices": []}
    devices = []
    for line in proc.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        serial, _, state = line.partition("\t")
        devices.append({"serial": serial.strip(), "state": state.strip() or "unknown"})
    ok = any(device["state"] == "device" for device in devices)
    detail = "device connected" if ok else "no device connected"
    return {"ok": ok, "detail": detail, "devices": devices, "adbPath": adb_path}


def build_status_payload() -> dict:
    bootstrap_runtime()
    if vta.OPENCLAW_PARSE_MODE == "openai_direct":
        parse_model = vta.OPENAI_MODEL_ID
        parse_runtime = "OpenAI direct"
    elif vta.OPENCLAW_PARSE_MODE == "deepseek_direct":
        parse_model = vta.DEEPSEEK_MODEL_ID
        parse_runtime = "DeepSeek direct"
    elif vta.OPENCLAW_PARSE_MODE == "openclaw_cloud":
        parse_model = "remote-main"
        parse_runtime = "OpenClaw cloud"
    else:
        parse_model = vta.OPENCLAW_MODEL_ID
        parse_runtime = "OpenClaw"
    return {
        "ok": True,
        "mode": vta.OPENCLAW_PARSE_MODE,
        "runtime": parse_runtime,
        "model": parse_model,
        "contacts": load_contacts_summary(),
        "adb": probe_adb_devices(),
        "examples": [
            "给10086打电话",
            "给12306发一条我晚点到",
            "有没有新短信",
        ],
    }


def run_voice_command(
    voice_text: str,
    *,
    clarification_context: dict | None = None,
    dry_run: bool = False,
    no_tts: bool = True,
    limit: int = 5,
    auto_send: bool = False,
) -> dict:
    bootstrap_runtime()
    logs: list[str] = []

    def log(message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        logs.append(f"[{stamp}] {message}")

    started_at = time.time()
    if vta.OPENCLAW_PARSE_MODE == "openai_direct":
        parse_model = vta.OPENAI_MODEL_ID
        parse_runtime = "OpenAI direct"
    elif vta.OPENCLAW_PARSE_MODE == "deepseek_direct":
        parse_model = vta.DEEPSEEK_MODEL_ID
        parse_runtime = "DeepSeek direct"
    elif vta.OPENCLAW_PARSE_MODE == "openclaw_cloud":
        parse_model = "remote-main"
        parse_runtime = "OpenClaw cloud"
    else:
        parse_model = vta.OPENCLAW_MODEL_ID
        parse_runtime = "OpenClaw"
    log(f"voice_text={voice_text!r}")
    if clarification_context:
        log(f"clarification_context={clarification_context!r}")
    log(f"parse runtime={parse_runtime}, mode={vta.OPENCLAW_PARSE_MODE}, model={parse_model}")

    fallback_used = False
    parse_error = ""
    parse_user_text = vta.compose_parse_user_text(voice_text, clarification_context)
    try:
        t0 = time.time()
        raw_reply = vta.call_openclaw(vta.INTENT_PROMPT_TEMPLATE.format(user_text=parse_user_text))
        parse_elapsed = time.time() - t0
        log(f"model reply in {parse_elapsed:.1f}s: {raw_reply}")
        intent = vta.parse_intent(raw_reply)
    except Exception as exc:
        fallback_used = True
        parse_error = str(exc)
        vta.OPENCLAW_AVAILABLE = False
        log(f"model parse failed, fallback to local rules: {exc!r}")
        intent = vta.fallback_intent(voice_text, vta.DEFAULT_CONTACTS)
        parse_elapsed = None

    log(f"intent={intent}")
    response = {
        "ok": True,
        "voiceText": voice_text,
        "intent": intent,
        "logs": logs,
        "dryRun": dry_run,
        "parse": {
            "runtime": parse_runtime,
            "mode": vta.OPENCLAW_PARSE_MODE,
            "model": parse_model,
            "fallbackUsed": fallback_used,
            "elapsedSec": parse_elapsed,
            "error": parse_error,
        },
        "timing": {"totalSec": 0.0},
    }

    if intent.get("needs_clarification"):
        question = intent.get("clarify_question") or "你是想让我帮你打电话、发短信，还是读短信？"
        original_voice_text = (
            str(clarification_context.get("originalVoiceText") or "").strip()
            if clarification_context
            else voice_text
        )
        response["clarificationRequired"] = True
        response["pendingClarification"] = {
            "question": question,
            "context": {
                "originalVoiceText": original_voice_text,
                "question": question,
                "summary": intent.get("summary", ""),
            },
        }
        log(f"clarification required: {question}")
        response["timing"]["totalSec"] = round(time.time() - started_at, 2)
        return response

    if dry_run:
        log("dry-run: skip device action")
        response["timing"]["totalSec"] = round(time.time() - started_at, 2)
        return response

    vta.ensure_android_device()
    action = intent["action"]
    if action == "read_inbox":
        adapter = vta.build_adapter("read_inbox")
        llm_caller = vta.call_openclaw if vta.OPENCLAW_AVAILABLE and vta.OPENCLAW_USE_FOR_SMS_CLASSIFICATION else None
        result = adapter.execute({"limit": int(limit), "llm_caller": llm_caller})
        log(f"read_inbox result: ok={result.ok} detail={result.detail}")
        if result.ok:
            summary_llm = vta.call_openclaw if vta.OPENCLAW_AVAILABLE else None
            elder_summary = summarize_inbox_for_elder(
                list(result.payload or []),
                load_contacts_summary(),
                intent=intent,
                llm_caller=summary_llm,
            )
            response["elderSummary"] = elder_summary
        if result.ok and not no_tts and result.payload:
            try:
                from tts_service import preheat, speak

                kind = preheat()
                log(f"tts engine={kind}")
                speech = response.get("elderSummary", {}).get("speech") or f"你有 {len(result.payload)} 条新消息。"
                speak(speech, blocking=True)
            except Exception as exc:
                log(f"tts failed: {exc!r}")
        response["result"] = _json_ready(result)
        response["timing"]["totalSec"] = round(time.time() - started_at, 2)
        response["ok"] = bool(result.ok)
        return response

    target = intent.get("target", "")
    content = intent.get("content", "")
    phone = vta.safe_resolve_phone(target, vta.DEFAULT_CONTACTS)
    log(f"resolved target={target!r} -> phone={phone}")
    adapter = vta.build_adapter(action)
    params = {"phone": phone}
    if action == "send_sms":
        params["content"] = content
        params["auto_send"] = bool(auto_send)
        log(f"sms auto_send={bool(auto_send)}")
    result = adapter.execute(params)
    log(f"{action} result: ok={result.ok} detail={result.detail}")
    response["result"] = _json_ready(result)
    response["timing"]["totalSec"] = round(time.time() - started_at, 2)
    response["ok"] = bool(result.ok)
    return response


class DemoHandler(BaseHTTPRequestHandler):
    server_version = "ClawEaseDemo/0.1"

    def log_message(self, fmt: str, *args) -> None:
        return

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _try_static(self, request_path: str) -> bool:
        relative = request_path.lstrip("/") or "index.html"
        target = (STATIC_DIR / relative).resolve()
        try:
            target.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return False
        if not target.exists() or not target.is_file():
            return False
        content_type, _ = mimetypes.guess_type(str(target))
        self._send_file(target, content_type or "application/octet-stream")
        return True

    def _read_json(self) -> dict:
        raw_len = self.headers.get("Content-Length", "0").strip()
        size = int(raw_len or "0")
        raw = self.rfile.read(size) if size > 0 else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            view = (parse_qs(parsed.query).get("view") or ["dual"])[0].strip().lower()
            page = {
                "elder": "elder.html",
                "operator": "operator.html",
                "dual": "index.html",
            }.get(view, "index.html")
            return self._send_file(STATIC_DIR / page, "text/html; charset=utf-8")
        if parsed.path == "/api/status":
            try:
                return self._send_json(build_status_payload())
            except Exception as exc:
                return self._send_json({"ok": False, "error": str(exc)}, status=500)
        if parsed.path == "/api/health":
            return self._send_json({"ok": True, "service": "clawease-demo"})
        if self._try_static(parsed.path):
            return
        return self._send_json({"ok": False, "error": "not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            return self._send_json({"ok": False, "error": "not found"}, status=404)
        try:
            payload = self._read_json()
        except Exception:
            return self._send_json({"ok": False, "error": "invalid json"}, status=400)

        voice_text = str(payload.get("voiceText") or "").strip()
        if not voice_text:
            return self._send_json({"ok": False, "error": "voiceText is required"}, status=400)

        if not RUN_LOCK.acquire(blocking=False):
            return self._send_json(
                {"ok": False, "error": "another command is already running"},
                status=409,
            )
        try:
            result = run_voice_command(
                voice_text,
                clarification_context=payload.get("clarificationContext") if isinstance(payload.get("clarificationContext"), dict) else None,
                dry_run=bool(payload.get("dryRun", False)),
                no_tts=bool(payload.get("noTts", True)),
                limit=int(payload.get("limit", 5) or 5),
                auto_send=bool(payload.get("autoSend", False)),
            )
            return self._send_json(result)
        except Exception as exc:
            return self._send_json(
                {
                    "ok": False,
                    "error": str(exc),
                    "traceback": traceback.format_exc(limit=6),
                },
                status=500,
            )
        finally:
            RUN_LOCK.release()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if not STATIC_DIR.exists():
        raise SystemExit(f"Missing static dir: {STATIC_DIR}")

    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"[clawease-demo] http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[clawease-demo] stopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

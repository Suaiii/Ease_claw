from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OPENCLAW_DIR = r"E:\aNB\Ease-claw\openclaw"
WORKSPACE_ROOT = Path(r"E:\aNB\Ease-claw")
DEFAULT_CONTACTS = WORKSPACE_ROOT / "contacts.json"
DEFAULT_ENV = WORKSPACE_ROOT / ".env"
START_BAT = WORKSPACE_ROOT / "start.bat"
DEFAULT_ADB = (
    WORKSPACE_ROOT
    / ".conda"
    / "clawease"
    / "Lib"
    / "site-packages"
    / "adbutils"
    / "binaries"
    / "adb.exe"
)

INTENT_PROMPT_TEMPLATE = (
    "你是老人手机助手的中文意图解析器。"
    "只做一件事：把用户的一句中文命令解析成一个 JSON 对象。"
    "action 只能是 call、send_sms、read_inbox 之一。"
    "规则："
    "call 表示打电话，target 填联系人姓名或号码，content 置空；"
    "send_sms 表示发短信，target 填联系人姓名或号码，content 填短信正文；"
    "read_inbox 表示读取最新短信，target 和 content 都置空。"
    "只返回一个 JSON 对象，不要解释，不要代码块。"
    '格式：{{"action":"call|send_sms|read_inbox","target":"...","content":"..."}}。'
    "用户输入：{user_text}"
)

CALL_HINTS = ("打电话", "拨号", "拨个电话", "拨通", "呼叫")
SMS_HINTS = ("发短信", "发个短信", "发一条", "发消息", "发个消息", "告诉", "通知")
INBOX_HINTS = ("新短信", "收件箱", "验证码", "有没有短信", "有没有消息", "读短信", "查短信")
SMS_PREFIX_PATTERNS = (
    r"^给{target}发一条短信",
    r"^给{target}发个短信",
    r"^给{target}发一条",
    r"^给{target}发消息",
    r"^给{target}发个消息",
    r"^给{target}说",
    r"^告诉{target}",
    r"^通知{target}",
)


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be > 0, got {value}")
    return value


OPENCLAW_AGENT_ID = "main"
OPENCLAW_MODEL_ID = "google/gemini-2.5-flash"
OPENCLAW_PARSE_MODE = "model_run"
OPENAI_MODEL_ID = "gpt-5.4-mini"
OPENCLAW_AGENT_TIMEOUT_SEC = 210
OPENCLAW_PROCESS_TIMEOUT_SEC = 240
OPENCLAW_USE_FOR_SMS_CLASSIFICATION = False
OPENCLAW_AVAILABLE = True


def refresh_runtime_flags() -> None:
    global OPENCLAW_AGENT_ID
    global OPENCLAW_MODEL_ID
    global OPENCLAW_PARSE_MODE
    global OPENAI_MODEL_ID
    global OPENCLAW_AGENT_TIMEOUT_SEC
    global OPENCLAW_PROCESS_TIMEOUT_SEC
    global OPENCLAW_USE_FOR_SMS_CLASSIFICATION

    OPENCLAW_AGENT_ID = os.environ.get("OPENCLAW_AGENT_ID", "main").strip() or "main"
    OPENCLAW_MODEL_ID = (
        os.environ.get("OPENCLAW_MODEL_ID", "google/gemini-2.5-flash").strip()
        or "google/gemini-2.5-flash"
    )
    OPENCLAW_PARSE_MODE = (
        os.environ.get("OPENCLAW_PARSE_MODE", "model_run").strip().lower() or "model_run"
    )
    OPENAI_MODEL_ID = os.environ.get("OPENAI_MODEL_ID", "gpt-5.4-mini").strip() or "gpt-5.4-mini"
    OPENCLAW_AGENT_TIMEOUT_SEC = _env_int("OPENCLAW_AGENT_TIMEOUT_SEC", 210)
    OPENCLAW_PROCESS_TIMEOUT_SEC = _env_int(
        "OPENCLAW_PROCESS_TIMEOUT_SEC", OPENCLAW_AGENT_TIMEOUT_SEC + 30
    )
    OPENCLAW_USE_FOR_SMS_CLASSIFICATION = (
        os.environ.get("OPENCLAW_USE_FOR_SMS_CLASSIFICATION", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )


refresh_runtime_flags()


def load_env(env_path: Path = DEFAULT_ENV) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)



def load_start_proxy_env(start_path: Path = START_BAT) -> None:
    if not start_path.exists():
        return
    for line in start_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.lower().startswith("set ") or "=" not in line:
            continue
        body = line[4:]
        key, _, value = body.partition("=")
        key = key.strip()
        value = value.strip()
        if key in {"HTTP_PROXY", "HTTPS_PROXY"} and value:
            os.environ.setdefault(key, value)
            os.environ.setdefault(key.lower(), value)



def configure_runtime_env() -> None:
    load_start_proxy_env()
    if DEFAULT_ADB.exists():
        os.environ.setdefault("ADBUTILS_ADB_PATH", str(DEFAULT_ADB))



def current_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    if DEFAULT_ADB.exists():
        env.setdefault("ADBUTILS_ADB_PATH", str(DEFAULT_ADB))
    return env



def _extract_openclaw_text(envelope: dict) -> str:
    payloads = envelope.get("payloads") or []
    if payloads:
        return (payloads[0] or {}).get("text", "")
    outputs = envelope.get("outputs") or []
    if outputs:
        return (outputs[0] or {}).get("text", "")
    return ""



def _extract_openai_output_text(payload: dict) -> str:
    text = (payload.get("output_text") or "").strip()
    if text:
        return text
    for item in payload.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") == "output_text":
                value = (content.get("text") or "").strip()
                if value:
                    return value
    return ""


def call_openai_direct(prompt: str) -> str:
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing for openai_direct mode")

    body = json.dumps(
        {
            "model": OPENAI_MODEL_ID,
            "input": prompt,
            "reasoning": {"effort": "low"},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            req,
            timeout=min(OPENCLAW_PROCESS_TIMEOUT_SEC, 60),
        ) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI request failed: {exc}") from exc

    text = _extract_openai_output_text(payload)
    if not text:
        raise RuntimeError(f"OpenAI emitted no text output: {payload!r}")
    return text


def call_openclaw(prompt: str) -> str:
    global OPENCLAW_AVAILABLE
    if not OPENCLAW_AVAILABLE:
        raise RuntimeError("OpenClaw temporarily disabled after previous failure")
    if OPENCLAW_PARSE_MODE == "openai_direct":
        return call_openai_direct(prompt)
    if OPENCLAW_PARSE_MODE == "agent":
        cmd = [
            "node",
            "openclaw.mjs",
            "agent",
            "--local",
            "--agent",
            OPENCLAW_AGENT_ID,
            "--json",
            "--thinking",
            "off",
            "--timeout",
            str(OPENCLAW_AGENT_TIMEOUT_SEC),
            "--message",
            prompt,
        ]
    else:
        cmd = [
            "node",
            "openclaw.mjs",
            "infer",
            "model",
            "run",
            "--local",
            "--model",
            OPENCLAW_MODEL_ID,
            "--json",
            "--prompt",
            prompt,
        ]
    proc = subprocess.run(
        cmd,
        cwd=OPENCLAW_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=False,
        timeout=OPENCLAW_PROCESS_TIMEOUT_SEC,
        env=current_subprocess_env(),
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if proc.returncode != 0:
        raise RuntimeError(
            f"OpenClaw exited {proc.returncode}. stdout={stdout!r} stderr={stderr!r}"
        )
    for stream in (stdout, stderr):
        idx = stream.find("{")
        if idx < 0:
            continue
        try:
            envelope, _ = json.JSONDecoder().raw_decode(stream[idx:])
        except json.JSONDecodeError:
            continue
        text = _extract_openclaw_text(envelope)
        if text:
            return text
    raise RuntimeError(f"OpenClaw emitted no JSON envelope. stdout={stdout!r} stderr={stderr!r}")



def load_contacts(contacts_path: Path) -> dict:
    if not contacts_path.exists():
        raise RuntimeError(f"contacts.json missing: {contacts_path}")
    return json.loads(contacts_path.read_text(encoding="utf-8"))



def find_target_candidate(user_text: str, contacts: dict) -> str:
    text = user_text.strip()
    for name in sorted((key for key in contacts.keys() if key and not key.startswith("_")), key=len, reverse=True):
        if name in text:
            return name
    number_match = re.search(r"(?<!\d)(\+?\d{3,})(?!\d)", text)
    if number_match:
        return number_match.group(1)
    return ""



def normalize_sms_content(user_text: str, target: str) -> str:
    text = user_text.strip()
    for pattern in SMS_PREFIX_PATTERNS:
        text = re.sub(pattern.format(target=re.escape(target)), "", text)
    return text.strip(" ，。,.:")



def fallback_intent(user_text: str, contacts_path: Path) -> dict:
    text = user_text.strip()
    contacts = load_contacts(contacts_path)
    target = find_target_candidate(text, contacts)

    if any(keyword in text for keyword in CALL_HINTS):
        if not target:
            raise RuntimeError(f"fallback could not resolve call target: {text!r}")
        return {"action": "call", "target": target, "content": ""}

    if any(marker in text for marker in SMS_HINTS):
        if not target:
            raise RuntimeError(f"fallback could not resolve sms target: {text!r}")
        content = normalize_sms_content(text, target)
        if not content:
            raise RuntimeError(f"fallback could not resolve sms content: {text!r}")
        return {"action": "send_sms", "target": target, "content": content}

    if any(marker in text for marker in INBOX_HINTS):
        return {"action": "read_inbox", "target": "", "content": ""}

    raise RuntimeError(f"fallback could not resolve intent: {text!r}")



def parse_intent(inner_text: str) -> dict:
    text = inner_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    idx = text.find("{")
    if idx < 0:
        raise RuntimeError(f"intent JSON not found: {inner_text!r}")
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[idx:])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"intent JSON parse failed: {exc}: {inner_text!r}") from exc
    action = str(obj.get("action", "")).strip()
    if action not in {"call", "send_sms", "read_inbox"}:
        raise RuntimeError(f"invalid intent action: {obj!r}")
    return {
        "action": action,
        "target": str(obj.get("target", "")).strip(),
        "content": str(obj.get("content", "")).strip(),
    }



def build_adapter(action: str):
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    if action == "call":
        from messenger.call import CallAdapter

        return CallAdapter()
    if action == "send_sms":
        from messenger.sms import SmsAdapter

        return SmsAdapter()
    if action == "read_inbox":
        from messenger.inbox import InboxReaderAdapter

        return InboxReaderAdapter()
    raise RuntimeError(f"unknown action: {action!r}")



def safe_resolve_phone(name: str, contacts_path: Path) -> str:
    if re.fullmatch(r"\+?\d{3,}", name or ""):
        return name
    contacts = load_contacts(contacts_path)
    entry = contacts.get(name)
    if not entry:
        raise RuntimeError(f"contact {name!r} not found in {contacts_path}")
    phone = (entry.get("phone") or "").strip()
    if not phone:
        raise RuntimeError(f"contact {name!r} has empty phone in {contacts_path}")
    return phone



def ensure_android_device() -> None:
    adb_path = os.environ.get("ADBUTILS_ADB_PATH")
    if not adb_path:
        raise RuntimeError("ADB is not configured; expected ADBUTILS_ADB_PATH")
    proc = subprocess.run(
        [adb_path, "devices"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        env=current_subprocess_env(),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"adb devices failed: {proc.stderr.strip() or proc.stdout.strip()}")
    lines = [line.strip() for line in proc.stdout.splitlines()[1:] if line.strip()]
    if not any("\tdevice" in line for line in lines):
        raise RuntimeError(
            f"no Android device/emulator detected; start LDPlayer or connect a phone first (adb={adb_path})"
        )



def do_read_inbox(limit: int, skip_tts: bool) -> int:
    adapter = build_adapter("read_inbox")
    llm_caller = (
        call_openclaw
        if OPENCLAW_AVAILABLE and OPENCLAW_USE_FOR_SMS_CLASSIFICATION
        else None
    )
    result = adapter.execute({"limit": limit, "llm_caller": llm_caller})
    print(f"[clawease] read_inbox ok={result.ok} detail={result.detail!r}")
    if not result.ok:
        return 1

    items = result.payload or []
    print(f"[clawease] classified {len(items)} sms item(s)")
    for i, item in enumerate(items, 1):
        verdict = item["verdict"]
        print(
            f"  {i}. [{verdict.category}] {item['sender']}: {item['body'][:40]}..."
            f"  (conf={verdict.confidence:.2f})"
        )

    if skip_tts or not items:
        return 0

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from tts_local import preheat, speak

        kind = preheat()
        print(f"[clawease] tts engine={kind}, reading summary...")
        speak(f"你有 {len(items)} 条新消息。", blocking=True)
        for i, item in enumerate(items, 1):
            speak(f"第 {i} 条。{item['readable']}", blocking=True)
    except Exception as exc:
        print(f"[clawease] TTS failed but main flow is okay: {exc!r}")
    return 0



def main() -> int:
    global OPENCLAW_AVAILABLE

    ap = argparse.ArgumentParser()
    ap.add_argument("--voice-text", required=True, help="Natural-language user command")
    ap.add_argument("--contacts", default=str(DEFAULT_CONTACTS))
    ap.add_argument("--env", default=str(DEFAULT_ENV))
    ap.add_argument("--dry-run", action="store_true", help="Only parse intent")
    ap.add_argument("--limit", type=int, default=5, help="Inbox read limit")
    ap.add_argument("--no-tts", action="store_true", help="Disable TTS for inbox reads")
    args = ap.parse_args()

    load_env(Path(args.env))
    configure_runtime_env()
    refresh_runtime_flags()

    print(f"[clawease] voice_text={args.voice_text!r}")
    parse_model = OPENAI_MODEL_ID if OPENCLAW_PARSE_MODE == "openai_direct" else OPENCLAW_MODEL_ID
    parse_runtime = "OpenAI direct" if OPENCLAW_PARSE_MODE == "openai_direct" else "OpenClaw"
    print(
        f"[clawease] calling {parse_runtime} for intent "
        f"(mode={OPENCLAW_PARSE_MODE}, model={parse_model}, timeout={OPENCLAW_AGENT_TIMEOUT_SEC}s) ..."
    )
    try:
        t0 = time.time()
        inner = call_openclaw(INTENT_PROMPT_TEMPLATE.format(user_text=args.voice_text))
        print(f"[clawease] parse reply in {time.time() - t0:.1f}s: {inner!r}")
        intent = parse_intent(inner)
    except Exception as exc:
        OPENCLAW_AVAILABLE = False
        print(f"[clawease] model parse failed, fallback to local rules: {exc!r}")
        intent = fallback_intent(args.voice_text, Path(args.contacts))

    action = intent["action"]
    print(f"[clawease] intent: {intent}")

    if args.dry_run:
        print("[clawease] --dry-run: skip device action")
        return 0

    if action == "read_inbox":
        ensure_android_device()
        return do_read_inbox(args.limit, args.no_tts)

    target = intent.get("target", "")
    content = intent.get("content", "")
    phone = safe_resolve_phone(target, Path(args.contacts))
    print(f"[clawease] route: {action} -> {phone} (from {target!r})")

    ensure_android_device()
    adapter = build_adapter(action)
    params = {"phone": phone}
    if action == "send_sms":
        params["content"] = content
    result = adapter.execute(params)
    print(f"[clawease] result: ok={result.ok} detail={result.detail!r}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())

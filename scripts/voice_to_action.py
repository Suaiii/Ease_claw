from __future__ import annotations

import argparse
import json
import os
import re
import socket
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
OPENCLAW_CLOUD_STATE_DIR = WORKSPACE_ROOT / ".openclaw-cloud"
OPENCLAW_CLOUD_RELAY = WORKSPACE_ROOT / "scripts" / "start_openclaw_cloud_relay.ps1"
OPENCLAW_CLOUD_HELPER = WORKSPACE_ROOT / "scripts" / "openclaw_cloud_intent.mjs"
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
    "你是面向老人/视障用户的中文通讯助手语义解析器。"
    "你不只是做动作分类，还要提炼老人话里的关键信息。"
    "只返回一个 JSON 对象，不要解释，不要代码块。"
    "action 只能是 call、send_sms、read_inbox 之一。"
    "规则："
    "call 表示打电话，target 填联系人姓名或号码，content 置空；"
    "send_sms 表示发短信，target 填联系人姓名或号码，content 填短信正文；"
    "read_inbox 表示读取最新短信，target 和 content 都置空。"
    "summary 用一句自然中文总结老人真正想做的事；"
    "key_points 是 1 到 3 条短语，提取关键信息；"
    "focus_tags 从 known_contact、verification_code、fraud_risk、urgent、reminder 中选择 0 到 3 个；"
    "risk_flags 从 fraud_risk、unclear_target、unclear_content 中选择；"
    "needs_clarification 是 true/false；"
    "clarify_question 仅在需要澄清时填写一句追问，否则置空。"
    '格式：{{"action":"call|send_sms|read_inbox","target":"...","content":"...","summary":"...","key_points":["..."],"focus_tags":["..."],"risk_flags":["..."],"needs_clarification":false,"clarify_question":""}}。'
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


OPENCLAW_AGENT_ID = "clawease-intent"
OPENCLAW_MODEL_ID = "google/gemini-2.5-flash"
OPENCLAW_PARSE_MODE = "model_run"
OPENAI_MODEL_ID = "gpt-5.4-mini"
DEEPSEEK_MODEL_ID = "deepseek-chat"
OPENCLAW_CLOUD_URL = "ws://127.0.0.1:31879"
OPENCLAW_AGENT_TIMEOUT_SEC = 210
OPENCLAW_PROCESS_TIMEOUT_SEC = 240
OPENCLAW_USE_FOR_SMS_CLASSIFICATION = False
OPENCLAW_SESSION_ID = ""
OPENCLAW_AVAILABLE = True


def refresh_runtime_flags() -> None:
    global OPENCLAW_AGENT_ID
    global OPENCLAW_MODEL_ID
    global OPENCLAW_PARSE_MODE
    global OPENAI_MODEL_ID
    global DEEPSEEK_MODEL_ID
    global OPENCLAW_CLOUD_URL
    global OPENCLAW_AGENT_TIMEOUT_SEC
    global OPENCLAW_PROCESS_TIMEOUT_SEC
    global OPENCLAW_USE_FOR_SMS_CLASSIFICATION
    global OPENCLAW_SESSION_ID

    OPENCLAW_AGENT_ID = (
        os.environ.get("OPENCLAW_AGENT_ID", "clawease-intent").strip() or "clawease-intent"
    )
    OPENCLAW_MODEL_ID = (
        os.environ.get("OPENCLAW_MODEL_ID", "google/gemini-2.5-flash").strip()
        or "google/gemini-2.5-flash"
    )
    OPENCLAW_PARSE_MODE = (
        os.environ.get("OPENCLAW_PARSE_MODE", "model_run").strip().lower() or "model_run"
    )
    OPENAI_MODEL_ID = os.environ.get("OPENAI_MODEL_ID", "gpt-5.4-mini").strip() or "gpt-5.4-mini"
    DEEPSEEK_MODEL_ID = os.environ.get("DEEPSEEK_MODEL_ID", "deepseek-chat").strip() or "deepseek-chat"
    OPENCLAW_CLOUD_URL = (
        os.environ.get("OPENCLAW_CLOUD_URL", "ws://127.0.0.1:31879").strip()
        or "ws://127.0.0.1:31879"
    )
    OPENCLAW_AGENT_TIMEOUT_SEC = _env_int("OPENCLAW_AGENT_TIMEOUT_SEC", 210)
    OPENCLAW_PROCESS_TIMEOUT_SEC = _env_int(
        "OPENCLAW_PROCESS_TIMEOUT_SEC", OPENCLAW_AGENT_TIMEOUT_SEC + 30
    )
    OPENCLAW_USE_FOR_SMS_CLASSIFICATION = (
        os.environ.get("OPENCLAW_USE_FOR_SMS_CLASSIFICATION", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    OPENCLAW_SESSION_ID = os.environ.get("OPENCLAW_SESSION_ID", "").strip()


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


def _extract_deepseek_output_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = (choices[0] or {}).get("message") or {}
    return (message.get("content") or "").strip()


def call_deepseek_direct(prompt: str) -> str:
    api_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is missing for deepseek_direct mode")

    body = json.dumps(
        {
            "model": DEEPSEEK_MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
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
        raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DeepSeek request failed: {exc}") from exc

    text = _extract_deepseek_output_text(payload)
    if not text:
        raise RuntimeError(f"DeepSeek emitted no text output: {payload!r}")
    return text


def ensure_openclaw_cloud_relay() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.5)
    try:
        sock.connect(("127.0.0.1", 31879))
        return
    except OSError:
        pass
    finally:
        sock.close()

    if not OPENCLAW_CLOUD_RELAY.exists():
        raise RuntimeError(f"cloud relay script missing: {OPENCLAW_CLOUD_RELAY}")
    proc = subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(OPENCLAW_CLOUD_RELAY),
        ],
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        env=current_subprocess_env(),
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"failed to start cloud relay: stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )


def call_openclaw_cloud(prompt: str) -> str:
    ensure_openclaw_cloud_relay()
    if not OPENCLAW_CLOUD_HELPER.exists():
        raise RuntimeError(f"cloud helper missing: {OPENCLAW_CLOUD_HELPER}")
    env = current_subprocess_env()
    env.setdefault("OPENCLAW_CLOUD_STATE_DIR", str(OPENCLAW_CLOUD_STATE_DIR))
    env.setdefault("OPENCLAW_CLOUD_URL", OPENCLAW_CLOUD_URL)
    proc = subprocess.run(
        ["node", str(OPENCLAW_CLOUD_HELPER), prompt],
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=min(OPENCLAW_PROCESS_TIMEOUT_SEC, 60),
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"OpenClaw cloud exited {proc.returncode}. stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
    text = (proc.stdout or "").strip()
    if not text:
        raise RuntimeError(f"OpenClaw cloud emitted no text. stderr={proc.stderr!r}")
    return text


def call_openclaw(prompt: str) -> str:
    global OPENCLAW_AVAILABLE
    if not OPENCLAW_AVAILABLE:
        raise RuntimeError("OpenClaw temporarily disabled after previous failure")
    if OPENCLAW_PARSE_MODE == "openai_direct":
        return call_openai_direct(prompt)
    if OPENCLAW_PARSE_MODE == "deepseek_direct":
        return call_deepseek_direct(prompt)
    if OPENCLAW_PARSE_MODE == "openclaw_cloud":
        return call_openclaw_cloud(prompt)
    if OPENCLAW_PARSE_MODE == "agent":
        session_id = OPENCLAW_SESSION_ID or f"clawease-intent-{int(time.time() * 1000)}"
        cmd = [
            "node",
            "openclaw.mjs",
            "agent",
            "--local",
            "--agent",
            OPENCLAW_AGENT_ID,
            "--session-id",
            session_id,
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
    key_points = [text[:24]] if text else []

    if any(keyword in text for keyword in CALL_HINTS):
        if not target:
            raise RuntimeError(f"fallback could not resolve call target: {text!r}")
        return {
            "action": "call",
            "target": target,
            "content": "",
            "summary": f"老人想给{target}打电话。",
            "key_points": [f"联系人：{target}", "动作：打电话"],
            "focus_tags": ["known_contact"] if target in contacts else [],
            "risk_flags": [],
            "needs_clarification": False,
            "clarify_question": "",
        }

    if any(marker in text for marker in SMS_HINTS):
        if not target:
            raise RuntimeError(f"fallback could not resolve sms target: {text!r}")
        content = normalize_sms_content(text, target)
        if not content:
            raise RuntimeError(f"fallback could not resolve sms content: {text!r}")
        return {
            "action": "send_sms",
            "target": target,
            "content": content,
            "summary": f"老人想给{target}发短信，核心内容是：{content}",
            "key_points": [f"联系人：{target}", f"短信：{content[:18]}"],
            "focus_tags": ["known_contact"] if target in contacts else [],
            "risk_flags": [],
            "needs_clarification": False,
            "clarify_question": "",
        }

    if any(marker in text for marker in INBOX_HINTS):
        focus_tags = ["verification_code"] if "验证码" in text else []
        if any(flag in text for flag in ("诈骗", "可疑", "陌生")):
            focus_tags.append("fraud_risk")
        return {
            "action": "read_inbox",
            "target": "",
            "content": "",
            "summary": "老人想查看并听取最新短信里的重点信息。",
            "key_points": key_points or ["查看新短信"],
            "focus_tags": focus_tags,
            "risk_flags": [],
            "needs_clarification": False,
            "clarify_question": "",
        }

    raise RuntimeError(f"fallback could not resolve intent: {text!r}")



def parse_intent(inner_text: str) -> dict:
    text = inner_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    candidates = [m.start() for m in re.finditer(r"\{", text)]
    if not candidates:
        raise RuntimeError(f"intent JSON not found: {inner_text!r}")
    obj = None
    last_error = None
    for idx in candidates:
        try:
            parsed, _ = json.JSONDecoder().raw_decode(text[idx:])
        except json.JSONDecodeError as exc:
            last_error = exc
            parsed = _parse_relaxed_intent(text[idx:])
            if parsed is None:
                continue
        obj = parsed
        if isinstance(obj, dict) and obj.get("action") in {"call", "send_sms", "read_inbox"}:
            break
    if not isinstance(obj, dict):
        raise RuntimeError(f"intent JSON parse failed: {last_error}: {inner_text!r}")
    action = str(obj.get("action", "")).strip()
    if action not in {"call", "send_sms", "read_inbox"}:
        raise RuntimeError(f"invalid intent action: {obj!r}")
    def _string_list(value) -> list[str]:
        if not isinstance(value, list):
            return []
        items: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                items.append(text)
        return items[:3]

    return {
        "action": action,
        "target": str(obj.get("target", "")).strip(),
        "content": str(obj.get("content", "")).strip(),
        "summary": str(obj.get("summary", "")).strip(),
        "key_points": _string_list(obj.get("key_points")),
        "focus_tags": _string_list(obj.get("focus_tags")),
        "risk_flags": _string_list(obj.get("risk_flags")),
        "needs_clarification": bool(obj.get("needs_clarification", False)),
        "clarify_question": str(obj.get("clarify_question", "")).strip(),
    }


def _parse_relaxed_intent(raw: str) -> dict | None:
    def grab(name: str) -> str:
        match = re.search(rf'"{name}"\s*:\s*"(.*?)"', raw, re.DOTALL)
        if not match:
            return ""
        value = match.group(1).strip()
        if value == ",":
            return ""
        return value

    def grab_bool(name: str) -> bool:
        match = re.search(rf'"{name}"\s*:\s*(true|false)', raw, re.IGNORECASE)
        return bool(match and match.group(1).lower() == "true")

    def grab_list(name: str) -> list[str]:
        match = re.search(rf'"{name}"\s*:\s*\[(.*?)\]', raw, re.DOTALL)
        if not match:
            return []
        inner = match.group(1)
        return [item.strip() for item in re.findall(r'"(.*?)"', inner) if item.strip()][:3]

    action = grab("action")
    if action not in {"call", "send_sms", "read_inbox"}:
        return None
    return {
        "action": action,
        "target": grab("target"),
        "content": grab("content"),
        "summary": grab("summary"),
        "key_points": grab_list("key_points"),
        "focus_tags": grab_list("focus_tags"),
        "risk_flags": grab_list("risk_flags"),
        "needs_clarification": grab_bool("needs_clarification"),
        "clarify_question": grab("clarify_question"),
    }


def compose_parse_user_text(user_text: str, clarification_context: dict | None = None) -> str:
    text = (user_text or "").strip()
    if not clarification_context:
        return text
    original = str(clarification_context.get("originalVoiceText") or "").strip()
    question = str(clarification_context.get("question") or "").strip()
    prior_summary = str(clarification_context.get("summary") or "").strip()
    if not original:
        return text
    parts = [f"老人上一轮原话：{original}"]
    if prior_summary:
        parts.append(f"上一轮系统判断：{prior_summary}")
    if question:
        parts.append(f"系统追问：{question}")
    parts.append(f"老人这次补充回答：{text}")
    return "\n".join(parts)



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
        from elder_summary import summarize_inbox_for_elder
        from tts_service import preheat, speak

        contacts = load_contacts(DEFAULT_CONTACTS)
        contact_rows = [
            {"name": name, "phone": entry.get("phone", ""), "note": entry.get("note", "")}
            for name, entry in contacts.items()
            if name and not name.startswith("_") and isinstance(entry, dict)
        ]
        elder_summary = summarize_inbox_for_elder(
            items,
            contact_rows,
            intent={"summary": "查看并归纳短信重点", "focus_tags": []},
            llm_caller=call_openclaw if OPENCLAW_AVAILABLE else None,
        )

        kind = preheat()
        print(f"[clawease] tts engine={kind}, reading summary...")
        speak(elder_summary["speech"], blocking=True)
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
    if OPENCLAW_PARSE_MODE == "openai_direct":
        parse_model = OPENAI_MODEL_ID
        parse_runtime = "OpenAI direct"
    elif OPENCLAW_PARSE_MODE == "deepseek_direct":
        parse_model = DEEPSEEK_MODEL_ID
        parse_runtime = "DeepSeek direct"
    elif OPENCLAW_PARSE_MODE == "openclaw_cloud":
        parse_model = "remote-main"
        parse_runtime = "OpenClaw cloud"
    else:
        parse_model = OPENCLAW_MODEL_ID
        parse_runtime = "OpenClaw"
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

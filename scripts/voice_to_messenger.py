"""ClawEase — D5 pivot: 自然语言 → OpenClaw 意图解析 → MessengerAdapter 路由发送。

路由规则：
  LLM 解析出 {to, msg}；`to` 是联系人友好名（"妈妈"、"姐姐"、"文件传输助手"）。
  脚本在 contacts.json 里查这个名字，拿到 {channel, address} —— 发到具体渠道。
  `--channel` 参数可覆盖 contacts.json 的默认渠道。

用法：
  python voice_to_messenger.py --voice-text "告诉妈妈我吃过饭了"
  python voice_to_messenger.py --voice-text "..." --channel whatsapp
  python voice_to_messenger.py --voice-text "..." --dry-run

contacts.json 示例：
  {
    "妈妈":         {"channel": "whatsapp",   "address": "8613xxxxxxxxx"},
    "姐姐":         {"channel": "sms",        "address": "13800000000"},
    "文件传输助手": {"channel": "wechat_ui",  "address": "文件传输助手"}
  }
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

OPENCLAW_DIR = r"E:\aNB\Ease-claw\openclaw"
WORKSPACE_ROOT = Path(r"E:\aNB\Ease-claw")
DEFAULT_CONTACTS = WORKSPACE_ROOT / "contacts.json"
DEFAULT_ENV = WORKSPACE_ROOT / ".env"

INTENT_PROMPT_TEMPLATE = (
    "你是意图解析器。用户说一句中文，请解析：to=要发给的联系人名（保留原名），"
    "msg=消息正文（改写成第一人称自然陈述句，去掉\"告诉、帮我说、发一条、告知\"等指令词）。"
    "严格输出：只输出 JSON 对象一行，不要代码块标记，不要解释。"
    "示例：输入\"告诉妈妈我现在有空\"→{{\"to\":\"妈妈\",\"msg\":\"我现在有空\"}}。"
    "现在解析：{user_text}"
)


def load_env(env_path: Path = DEFAULT_ENV) -> None:
    """极简 .env 装载。已有同名 env var 不覆盖，key=value 支持 # 注释。"""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def call_openclaw(prompt: str) -> str:
    cmd = [
        "pnpm", "dev", "agent",
        "--local", "--agent", "main",
        "--json", "--thinking", "off",
        "--message", prompt,
    ]
    proc = subprocess.run(
        cmd,
        cwd=OPENCLAW_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=True,
        timeout=360,
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    # pnpm 在 Windows PowerShell 下 JSON 体常被标记到 stderr，两边都试
    for stream in (stdout, stderr):
        idx = stream.find("{")
        if idx < 0:
            continue
        try:
            outer, _ = json.JSONDecoder().raw_decode(stream[idx:])
            return (outer.get("payloads") or [{}])[0].get("text", "")
        except json.JSONDecodeError:
            continue
    raise RuntimeError(f"OpenClaw 没吐 JSON。stdout={stdout!r} stderr={stderr!r}")


def parse_intent(inner_text: str) -> tuple[str, str]:
    t = inner_text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        t = "\n".join(lines[1:-1]).strip()
    obj = json.loads(t)
    to, msg = obj.get("to"), obj.get("msg")
    if not to or not msg:
        raise RuntimeError(f"意图 JSON 字段缺失：{obj!r}")
    return to, msg


def resolve_recipient(
    name: str,
    contacts_path: Path,
    channel_override: str | None,
) -> tuple[str, str]:
    """从 contacts.json 查 name → (channel, address)。

    覆盖规则：--channel 显式指定 > contacts.json 配置。
    没配置联系人且有 --channel：把 name 当作原始地址（手机号/微信名）直接用。
    """
    contacts = {}
    if contacts_path.exists():
        contacts = json.loads(contacts_path.read_text(encoding="utf-8"))
    if name in contacts:
        entry = contacts[name]
        channel = channel_override or entry.get("channel")
        address = entry.get("address") or ""
        if not channel:
            raise RuntimeError(f"联系人 {name!r} 缺 channel 字段（contacts.json）")
        if not address:
            raise RuntimeError(f"联系人 {name!r} 的 address 是空（contacts.json 还没填）")
        return channel, address
    if channel_override:
        return channel_override, name
    raise RuntimeError(
        f"联系人 {name!r} 不在 {contacts_path}，且没指定 --channel。"
        f"先在 contacts.json 里加这个人，或者用 --channel 指定渠道"
    )


def build_adapter(channel: str):
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    if channel == "whatsapp":
        from messenger.whatsapp import WhatsAppAdapter
        return WhatsAppAdapter()
    if channel == "sms":
        from messenger.sms import SmsAdapter
        return SmsAdapter()
    if channel == "wechat_ui":
        from messenger.wechat_ui import WeChatUiAdapter
        return WeChatUiAdapter()
    raise RuntimeError(f"unknown channel: {channel!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice-text", required=True, help="用户说的自然语言")
    ap.add_argument(
        "--channel",
        choices=["whatsapp", "sms", "wechat_ui"],
        help="覆盖 contacts.json 里的默认渠道",
    )
    ap.add_argument("--contacts", default=str(DEFAULT_CONTACTS), help="联系人路由表路径")
    ap.add_argument("--env", default=str(DEFAULT_ENV), help=".env 凭证文件路径")
    ap.add_argument("--dry-run", action="store_true", help="只解析意图+路由，不真发")
    args = ap.parse_args()

    load_env(Path(args.env))

    prompt = INTENT_PROMPT_TEMPLATE.format(user_text=args.voice_text)
    print(f"[clawease] voice_text={args.voice_text!r}")
    print("[clawease] calling OpenClaw ...")
    t0 = time.time()
    inner = call_openclaw(prompt)
    print(f"[clawease] OpenClaw reply in {time.time() - t0:.1f}s: {inner!r}")

    to_name, msg = parse_intent(inner)
    print(f"[clawease] parsed intent: to={to_name!r} msg={msg!r}")

    channel, address = resolve_recipient(to_name, Path(args.contacts), args.channel)
    print(f"[clawease] route: {channel} → {address!r}")

    if args.dry_run:
        print("[clawease] --dry-run: 不发送")
        return 0

    adapter = build_adapter(channel)
    result = adapter.send(address, msg)
    print(f"[clawease] send result: ok={result.ok} detail={result.detail!r}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())

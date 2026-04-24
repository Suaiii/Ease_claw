"""
ClawEase — D5: 自然语言 → OpenClaw 意图解析 → uiautomator2 发微信消息

用法：
  python voice_to_wechat.py --voice-text "告诉文件传输助手我吃过饭了"

逻辑：
  1. 把用户这句中文包成 prompt 丢给 OpenClaw (Gemini 2.5 Flash)
  2. 抽出 {"to":..., "msg":...} JSON
  3. 调 wechat_send 把 msg 发给 to
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# 复用 D4 的发消息逻辑
sys.path.insert(0, str(Path(__file__).parent))
from wechat_send import open_chat_with, send_text  # noqa: E402
import uiautomator2 as u2  # noqa: E402

OPENCLAW_DIR = r"E:\aNB\Ease-claw\openclaw"

# 注意：必须写成单行字符串 —— Windows subprocess shell=True 会把多行参数在第一个换行处截断。
INTENT_PROMPT_TEMPLATE = (
    "你是意图解析器。用户说一句中文，请解析：to=要发给的联系人名（微信昵称/备注，保留原名），"
    "msg=消息正文（改写成第一人称自然陈述句，去掉\"告诉、帮我说、发一条、告知\"等指令词）。"
    "严格输出：只输出 JSON 对象一行，不要代码块标记，不要解释。"
    "示例：输入\"告诉文件传输助手我现在有空\"→{{\"to\":\"文件传输助手\",\"msg\":\"我现在有空\"}}。"
    "现在解析：{user_text}"
)


def call_openclaw(prompt: str) -> str:
    """调 pnpm dev agent 拿结构化 JSON 输出，返回 payloads[0].text（内层 JSON 串）"""
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
        shell=True,  # Windows 下 pnpm 是 .ps1 脚本，需要 shell
        timeout=360,  # pnpm 首次启动 + TS 编译 ~130s + LLM ~47s，留足余量
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    # Windows 下 pnpm 通过 PowerShell 脚本调用 node，node 的 JSON 输出常被 PS 标记成 stderr。
    # 两边都看：找到第一个 '{' 之后用 JSONDecoder.raw_decode 解完整对象。
    for stream_name, stream in (("stdout", stdout), ("stderr", stderr)):
        brace_idx = stream.find("{")
        if brace_idx < 0:
            continue
        try:
            outer, _ = json.JSONDecoder().raw_decode(stream[brace_idx:])
            break
        except json.JSONDecodeError:
            continue
    else:
        raise RuntimeError(f"OpenClaw 没吐 JSON。stdout={stdout!r} stderr={stderr!r}")
    payloads = outer.get("payloads") or []
    if not payloads:
        raise RuntimeError(f"OpenClaw 输出没 payloads: {outer!r}")
    inner_text = payloads[0].get("text", "")
    return inner_text


def parse_intent(inner_text: str) -> tuple[str, str]:
    """从 LLM 的文本里抽 {to, msg}。尽量宽松 —— 剥掉可能的代码栅栏。"""
    t = inner_text.strip()
    if t.startswith("```"):
        # 剥掉 ```json ... ``` 这种 markdown 壳
        lines = t.splitlines()
        t = "\n".join(lines[1:-1]).strip()
    obj = json.loads(t)
    to = obj.get("to")
    msg = obj.get("msg")
    if not to or not msg:
        raise RuntimeError(f"意图 JSON 字段缺失：{obj!r}")
    return to, msg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice-text", required=True, help="用户说的自然语言（文本；后续替换成 ASR 输出）")
    ap.add_argument("--screenshot", help="可选：发送后截一张屏")
    ap.add_argument("--dry-run", action="store_true", help="只解析意图，不真的发消息")
    args = ap.parse_args()

    prompt = INTENT_PROMPT_TEMPLATE.format(user_text=args.voice_text)

    print(f"[clawease] voice_text={args.voice_text!r}")
    print(f"[clawease] calling OpenClaw ...")
    t0 = time.time()
    inner = call_openclaw(prompt)
    print(f"[clawease] OpenClaw reply in {time.time() - t0:.1f}s: {inner!r}")

    to, msg = parse_intent(inner)
    print(f"[clawease] parsed intent: to={to!r} msg={msg!r}")

    if args.dry_run:
        print("[clawease] --dry-run: 不发送")
        return 0

    d = u2.connect()
    print(f"[clawease] connected to {d.info.get('productName')}")
    open_chat_with(d, to)
    send_text(d, msg)
    print(f"[clawease] sent ✅")

    if args.screenshot:
        time.sleep(0.8)
        d.screenshot(args.screenshot)
        print(f"[clawease] screenshot -> {args.screenshot}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""InboxReaderAdapter — 读系统收件箱 + 反诈分类。

实现策略（Layer 1 优先 A，失败回退 B）：
  A. `adb shell content query --uri content://sms/inbox`  —— 纯数据读取，跨 ROM 稳
  B. 打开系统短信 app → dump UI hierarchy 提正文  —— 回退，不在 Layer 1 默认开

params:
  limit: int = 5        最近 N 条
  llm_caller: Callable  注入分类用的 LLM 调用函数（voice_to_action 注）

payload:
  list[dict]  每条形如 {sender, body, date_ms, verdict: SpamVerdict}
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

from .base import ActionAdapter, ActionResult

# 让同级的 spam_categories 可 import
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# content query 行样式（简化）：
#   Row: 0 address=10086, body=您好，验证码..., date=1729456781234
ROW_SPLIT = re.compile(r"^\s*Row:\s+\d+\s+", re.MULTILINE)
FIELD_RE = re.compile(r"(address|body|date)=((?:(?!,\s+\w+=).)*)", re.DOTALL)


class InboxReaderAdapter(ActionAdapter):
    channel = "inbox"
    action = "read_inbox"

    def __init__(self, device: Any = None):
        import uiautomator2 as u2

        self.d = device or u2.connect()

    def execute(self, params: dict) -> ActionResult:
        limit = int(params.get("limit", 5) or 5)
        llm_caller: Callable[[str], str] | None = params.get("llm_caller")

        try:
            raw = self._query_sms(limit)
        except Exception as e:
            return ActionResult(self.channel, self.action, False, f"content query: {e!r}")

        rows = self._parse_rows(raw)[:limit]
        if not rows:
            return ActionResult(
                self.channel, self.action, True,
                "收件箱为空 / 无读权限",
                payload=[],
            )

        from spam_categories import classify_sms, compose_readable

        items = []
        for r in rows:
            verdict = classify_sms(r["body"], llm_caller=llm_caller)
            items.append({
                "sender": r["address"],
                "body": r["body"],
                "date_ms": r["date"],
                "verdict": verdict,
                "readable": compose_readable(verdict, sender=r["address"]),
            })
        return ActionResult(
            self.channel, self.action, True,
            f"read {len(items)} sms",
            payload=items,
        )

    def _query_sms(self, limit: int) -> str:
        """adb shell content query 读收件箱最近 limit 条，date 倒序。"""
        # --sort 要求 Android 10+；旧机型可能忽略。退化时 Python 端再排序。
        cmd = (
            "content query --uri content://sms/inbox "
            "--projection address:body:date "
            f'--sort "date DESC"'
        )
        out = self.d.shell(cmd)
        # uiautomator2 的 shell 返回 ShellResponse(output=..., exit_code=...)
        text = getattr(out, "output", None) or (out if isinstance(out, str) else str(out))
        return text or ""

    def _parse_rows(self, raw: str) -> list[dict]:
        """解析 content query 输出为 [{address, body, date(ms int)}]。
        content query 对有逗号/等号的 body 输出本就有歧义，这里做尽力解析：
          以 'Row: N ' 分段，每段按 address=/body=/date= 贪婪取。
        """
        rows: list[dict] = []
        for chunk in ROW_SPLIT.split(raw):
            chunk = chunk.strip()
            if not chunk:
                continue
            fields = {"address": "", "body": "", "date": 0}
            # 简化：按 ', 字段名=' 切段
            # 先定位 address=
            addr_m = re.search(r"address=([^,]*),\s*body=", chunk)
            body_date_m = re.search(r"body=(.*),\s*date=(\d+)\s*$", chunk, re.DOTALL)
            if addr_m and body_date_m:
                fields["address"] = (addr_m.group(1) or "").strip()
                fields["body"] = (body_date_m.group(1) or "").strip()
                try:
                    fields["date"] = int(body_date_m.group(2))
                except ValueError:
                    fields["date"] = 0
            else:
                # fallback：宽松匹配每个字段
                for m in FIELD_RE.finditer(chunk):
                    k, v = m.group(1), m.group(2).rstrip(",").strip()
                    if k == "date":
                        try:
                            fields[k] = int(v)
                        except ValueError:
                            fields[k] = 0
                    else:
                        fields[k] = v
            if fields["address"] or fields["body"]:
                rows.append(fields)
        rows.sort(key=lambda r: r["date"], reverse=True)
        return rows

    def healthcheck(self) -> ActionResult:
        try:
            info = self.d.info
        except Exception as e:
            return ActionResult(self.channel, self.action, False, f"adb: {e!r}")
        return ActionResult(
            self.channel, self.action, True,
            f"device={info.get('productName')}",
        )

from __future__ import annotations

import json
import re
from typing import Any, Callable


def _normalize_phone(value: str) -> str:
    text = str(value or "").strip()
    digits = re.sub(r"\D+", "", text)
    return digits or text


def _verdict_field(verdict: Any, field: str, default: Any = "") -> Any:
    if isinstance(verdict, dict):
        return verdict.get(field, default)
    return getattr(verdict, field, default)


def _contact_name(sender: str, contacts: list[dict]) -> str:
    sender_key = _normalize_phone(sender)
    for entry in contacts:
        phone = _normalize_phone(entry.get("phone", ""))
        if phone and phone == sender_key:
            return str(entry.get("name") or "").strip()
    return ""


def _body_snippet(text: str, limit: int = 22) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "……"


def _fallback_summary(items: list[dict], contacts: list[dict]) -> dict:
    known: list[tuple[str, str]] = []
    codes: list[tuple[str, str]] = []
    suspicious: list[tuple[str, str, str]] = []
    ordinary = 0

    for item in items:
        sender = str(item.get("sender") or "").strip()
        body = str(item.get("body") or "").strip()
        verdict = item.get("verdict")
        category = str(_verdict_field(verdict, "category", "正常") or "正常").strip()
        name = _contact_name(sender, contacts)
        sender_label = name or sender or "陌生号码"

        if name:
            known.append((sender_label, body))
        if category == "验证码":
            codes.append((sender_label, body))
        elif category not in {"正常", "话费订单"}:
            suspicious.append((sender_label, category, body))
        elif not name:
            ordinary += 1

    parts: list[str] = []
    if known:
        who, body = known[0]
        parts.append(f"{who}发来消息：{_body_snippet(body)}")
        if len(known) > 1:
            parts.append(f"另外还有{len(known) - 1}条来自已知联系人的消息。")
    if codes:
        sender_label, _ = codes[0]
        prefix = f"{sender_label}发来" if sender_label else ""
        parts.append(f"{prefix}{len(codes)}条验证码短信，不要告诉任何人。")
    if suspicious:
        cats = "、".join(sorted({cat for _, cat, _ in suspicious})[:2])
        sender_label, _, body = suspicious[0]
        parts.append(f"还有{len(suspicious)}条可疑短信，像{cats}这类先不要点链接。")
        parts.append(f"最要紧的一条来自{sender_label}：{_body_snippet(body)}")
    if not parts:
        if ordinary:
            parts.append(f"现在有{ordinary}条普通短信，没有明显风险。")
        else:
            parts.append("暂时没有新短信。")

    text = " ".join(part for part in parts if part).strip()
    return {"display": text, "speech": text, "source": "fallback"}


def summarize_inbox_for_elder(
    items: list[dict],
    contacts: list[dict],
    intent: dict | None = None,
    llm_caller: Callable[[str], str] | None = None,
) -> dict:
    if not items:
        text = "暂时没有新短信。"
        return {"display": text, "speech": text, "source": "fallback"}

    fallback = _fallback_summary(items, contacts)
    if llm_caller is None:
        return fallback

    structured = []
    for item in items[:5]:
        sender = str(item.get("sender") or "").strip()
        body = str(item.get("body") or "").strip()
        verdict = item.get("verdict")
        structured.append(
            {
                "sender": sender,
                "contact_name": _contact_name(sender, contacts),
                "category": str(_verdict_field(verdict, "category", "正常") or "正常").strip(),
                "readable": str(item.get("readable") or "").strip(),
                "body": body,
            }
        )

    prompt = (
        "你是老人短信助手。现在要把几条短信整理成一段给老人听的中文播报。"
        "要求："
        "1. 先说已知联系人的关键信息；"
        "2. 再提醒验证码或疑似诈骗短信；"
        "3. 语气温和、像真人，不要机械罗列；"
        "4. 不要编造，不要输出 JSON，不超过 120 个汉字。"
        f"用户当前诉求：{json.dumps(intent or {}, ensure_ascii=False)}。"
        f"短信列表：{json.dumps(structured, ensure_ascii=False)}"
    )
    try:
        text = " ".join((llm_caller(prompt) or "").split()).strip()
    except Exception:
        return fallback
    if not text:
        return fallback
    return {"display": text, "speech": text, "source": "openclaw"}

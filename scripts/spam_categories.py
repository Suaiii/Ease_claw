"""反诈 / 生活短信分类 skill（C 方案 Layer 1）。

5 类（2026-04-24 调整：中奖 → 话费订单，兼顾诈骗识别与生活信息归类）：
  1. 冒充银行      - 假装 ICBC/ABC/BOC/CCB 等要点链接/回电/转账（疑似诈骗）
  2. 冒充公检法    - 假装警察/法院/检察院/社保局要求配合调查（疑似诈骗）
  3. 话费订单      - 运营商（移动/联通/电信）话费账单、余额、充值、套餐类通知（合法业务）
  4. 快递通知      - 假装快递丢失/需重新投递/海关扣留要求操作（疑似诈骗）
  5. 验证码        - 含 4-8 位数字验证码（无论来源都警告"不要告诉任何人"）

分类走 OpenClaw agent（Gemini zero-shot），与 voice_to_action 用同一条通道。
分类只做朗读前缀标注，**不自动删除 / 不屏蔽**。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

CATEGORIES = ("正常", "冒充银行", "冒充公检法", "话费订单", "快递通知", "验证码")

SPAM_PROMPT_TEMPLATE = (
    "你是短信分类器。输入一条中文短信，判断属于以下 6 类哪一类："
    "（1）冒充银行：假装 ICBC/ABC/BOC/CCB/农行/建行等，要点链接/回电/转账；"
    "（2）冒充公检法：假装警察/法院/检察院/社保局要求配合调查；"
    "（3）话费订单：运营商（中国移动/中国联通/中国电信、10086/10010/10000）发送的话费账单、"
    "余额提醒、充值到账、套餐变更、流量通知等合法业务消息；"
    "（4）快递通知：假装快递丢失/需重新投递/海关扣留要求操作；"
    "（5）验证码：含 4-8 位数字验证码（无论来源，都归此类）；"
    "（6）正常：以上都不是。"
    '严格输出一个 JSON 对象（不要代码块不要解释）：{{"category": "...", "confidence": 0.0, "reason": "简短"}}'
    "短信内容：{sms_body}"
)

VERIFICATION_CODE_RE = re.compile(r"(验证码|校验码|动态码)[^\d]{0,8}(\d{4,8})")
PHONE_BILL_RE = re.compile(
    r"(中国移动|中国联通|中国电信|移动公司|联通公司|电信公司|10086|10010|10000)"
    r".{0,40}?"
    r"(话费|账单|订单|充值|套餐|余额|流量)"
)


@dataclass
class SpamVerdict:
    category: str          # 正常 / 冒充银行 / 冒充公检法 / 话费订单 / 快递通知 / 验证码
    confidence: float      # 0.0-1.0
    reason: str
    original: str


def _fallback_classify(sms_body: str) -> SpamVerdict:
    """LLM 不可用时的 regex 兜底。
    优先级：验证码 > 话费订单 > 正常。
    保持保守，只命中运营商明显关键词，避免把诈骗误分成 benign。
    """
    if VERIFICATION_CODE_RE.search(sms_body):
        return SpamVerdict("验证码", 0.7, "regex 命中验证码模式", sms_body)
    if PHONE_BILL_RE.search(sms_body):
        return SpamVerdict("话费订单", 0.6, "regex 命中运营商 + 话费/账单关键词", sms_body)
    return SpamVerdict("正常", 0.3, "fallback regex 未识别可疑模式", sms_body)


def classify_sms(
    sms_body: str,
    llm_caller: Callable[[str], str] | None = None,
) -> SpamVerdict:
    """分类一条短信。llm_caller 传 OpenClaw/Gemini 调用函数，返回 LLM raw text。
    llm_caller=None 时走 regex 兜底。"""
    if not sms_body or not sms_body.strip():
        return SpamVerdict("正常", 1.0, "空正文", sms_body)
    if llm_caller is None:
        return _fallback_classify(sms_body)

    prompt = SPAM_PROMPT_TEMPLATE.format(sms_body=sms_body)
    try:
        raw = llm_caller(prompt) or ""
    except Exception as e:
        verdict = _fallback_classify(sms_body)
        verdict.reason = f"LLM 调用失败({e!r})，走 regex 兜底：{verdict.reason}"
        return verdict

    obj = _extract_json(raw)
    if not obj:
        verdict = _fallback_classify(sms_body)
        verdict.reason = f"LLM 未吐合规 JSON，走 regex 兜底：{verdict.reason}"
        return verdict

    cat = obj.get("category", "").strip()
    if cat not in CATEGORIES:
        cat = "正常"
    conf = float(obj.get("confidence", 0.0) or 0.0)
    reason = str(obj.get("reason", "") or "")
    return SpamVerdict(cat, conf, reason, sms_body)


def _extract_json(raw: str) -> dict | None:
    s = raw.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        s = "\n".join(lines[1:-1]).strip()
    idx = s.find("{")
    if idx < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(s[idx:])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def readable_prefix(verdict: SpamVerdict) -> str:
    """生成 TTS 朗读前缀。
    - 正常：空字符串（正常朗读）
    - 验证码：警告不要告诉任何人（杀招）
    - 话费订单：中性业务标签（合法，不是诈骗）
    - 其他 3 类（冒充银行/公检法/快递通知）：疑似诈骗警告
    """
    cat = verdict.category
    if cat == "正常":
        return ""
    if cat == "验证码":
        return "【警告：这是验证码短信，不要告诉任何人】"
    if cat == "话费订单":
        return "【话费通知】"
    return f"【可疑：疑似{cat}诈骗，请谨慎】"


def compose_readable(verdict: SpamVerdict, sender: str = "") -> str:
    """完整朗读文本 = 前缀 + 发件人 + 正文。sender 可选。"""
    prefix = readable_prefix(verdict)
    who = f"来自{sender}：" if sender else ""
    return f"{prefix}{who}{verdict.original}"

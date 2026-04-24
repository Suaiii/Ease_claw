"""反诈短信分类 skill（C 方案 Layer 1）。

5 类（用户 2026-04-23 拍板，加验证码删虚拟货币）：
  1. 冒充银行      - 假装 ICBC/ABC/BOC/CCB 等要点链接/回电/转账
  2. 冒充公检法    - 假装警察/法院/检察院/社保局要求配合调查
  3. 中奖          - 声称中奖/幸运用户/抽中现金奖品要求领取
  4. 快递通知      - 假装快递丢失/需重新投递/海关扣留要求操作
  5. 验证码        - 含 4-8 位数字验证码（无论来源都警告"不要告诉任何人"）

分类走 OpenClaw agent（Gemini zero-shot），与 voice_to_action 用同一条通道。
分类只做朗读前缀标注，**不自动删除 / 不屏蔽**。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

CATEGORIES = ("正常", "冒充银行", "冒充公检法", "中奖", "快递通知", "验证码")

SPAM_PROMPT_TEMPLATE = (
    "你是短信分类器。输入一条中文短信，判断属于以下 6 类哪一类："
    "（1）冒充银行：假装 ICBC/ABC/BOC/CCB/农行/建行等，要点链接/回电/转账；"
    "（2）冒充公检法：假装警察/法院/检察院/社保局要求配合调查；"
    "（3）中奖：声称中奖/幸运用户/抽中现金奖品要求领取；"
    "（4）快递通知：假装快递丢失/需重新投递/海关扣留要求操作；"
    "（5）验证码：含 4-8 位数字验证码（无论来源，都归此类）；"
    "（6）正常：以上都不是。"
    '严格输出一个 JSON 对象（不要代码块不要解释）：{{"category": "...", "confidence": 0.0, "reason": "简短"}}'
    "短信内容：{sms_body}"
)

VERIFICATION_CODE_RE = re.compile(r"(验证码|校验码|动态码)[^\d]{0,8}(\d{4,8})")


@dataclass
class SpamVerdict:
    category: str          # 正常 / 冒充银行 / 冒充公检法 / 中奖 / 快递通知 / 验证码
    confidence: float      # 0.0-1.0
    reason: str
    original: str


def _fallback_classify(sms_body: str) -> SpamVerdict:
    """LLM 不可用时的 regex 兜底。只识别明显的验证码模式；其他当正常处理。"""
    if VERIFICATION_CODE_RE.search(sms_body):
        return SpamVerdict("验证码", 0.7, "regex 命中验证码模式", sms_body)
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
    - 验证码：警告不要告诉任何人
    - 其他 4 类：疑似诈骗警告
    """
    cat = verdict.category
    if cat == "正常":
        return ""
    if cat == "验证码":
        return "【警告：这是验证码短信，不要告诉任何人】"
    return f"【可疑：疑似{cat}诈骗，请谨慎】"


def compose_readable(verdict: SpamVerdict, sender: str = "") -> str:
    """完整朗读文本 = 前缀 + 发件人 + 正文。sender 可选。"""
    prefix = readable_prefix(verdict)
    who = f"来自{sender}：" if sender else ""
    return f"{prefix}{who}{verdict.original}"

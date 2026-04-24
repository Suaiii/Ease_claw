"""SmsAdapter — Android intent 驱动短信 compose（C 方案 Layer 1 主路径）。

流程：
  am start -a android.intent.action.SENDTO -d 'sms:XXX' --es sms_body "..." -p com.android.mms
→ 系统短信 app 打开 compose 页，号码 & 正文已预填
→ （可选）MIUI 若进到"会话列表"视图，自动点 switch_to_editor 进编辑器
→ 默认 **停在 editor，等老人按发送键**（对齐 CallAdapter 的 DIAL 哲学：每次代操作都要用户确认）
→ `auto_send=True` 才真的点发送按钮

为什么默认不自动发：
  `clawease_tech_decisions.md` 硬约束 #1 —— 所有代操作必须有用户确认。
  CallAdapter 用 DIAL 让老人按绿键，SmsAdapter 也应该让老人按发送键，保持对称。
  demo 录制可用 `auto_send=True` 一键演示。

不同 ROM 的系统短信 app 有差异（小米 MIUI / 华为 / 三星 / OPPO / AOSP）；
Layer 1 先针对 MIUI 写，其他 ROM D5d 真机碰到时再扩 selector。

params:
  phone:     str   接收号码（纯数字）
  content:   str   短信正文
  auto_send: bool  默认 False；True 时自动点发送按钮
  sms_pkg:   str   默认 "com.android.mms"（MIUI 系统短信），其他 ROM 可传 "com.google.android.apps.messaging" 等
"""
from __future__ import annotations

import re
import time
from typing import Any

from .base import ActionAdapter, ActionResult

DEFAULT_SMS_PKG = "com.android.mms"

# MIUI: 进到 compose 后可能先落在会话列表视图，先点这个切到编辑器
SWITCH_TO_EDITOR_SELECTORS = [
    dict(resourceId="com.android.mms:id/switch_to_editor"),
    dict(description="Editor mode"),
]

# 编辑器 EditText（用于显式清空+set_text，绕开 sms_body extra 在 "已有会话" 场景失效的问题）
EDIT_TEXT_SELECTORS = [
    dict(resourceId="com.android.mms:id/embedded_text_editor"),  # MIUI
    dict(className="android.widget.EditText"),  # 通用兜底
]

# 发送按钮 selector（优先级从高到低）
SEND_BTN_SELECTORS = [
    dict(resourceId="com.android.mms:id/send_button"),  # MIUI 确认
    dict(description="Send message"),
    dict(description="发送短信"),
    dict(text="发送"),
    dict(text="Send"),
    dict(descriptionContains="Send"),
    dict(resourceIdMatches=r".*(send_button|btn_send|sendButton).*"),
]


def _sanitize(phone: str) -> str:
    return re.sub(r"[^\d+]", "", phone or "")


def _escape_body(text: str) -> str:
    return text.replace('"', r'\"')


class SmsAdapter(ActionAdapter):
    channel = "sms"
    action = "send_sms"

    def __init__(self, device: Any = None):
        import uiautomator2 as u2

        self.d = device or u2.connect()

    def execute(self, params: dict) -> ActionResult:
        phone = _sanitize(params.get("phone", ""))
        content = params.get("content", "") or ""
        auto_send = bool(params.get("auto_send", False))
        sms_pkg = params.get("sms_pkg", DEFAULT_SMS_PKG)

        if not phone:
            return ActionResult(self.channel, self.action, False, "no phone in params")
        if not content:
            return ActionResult(self.channel, self.action, False, "empty content")

        body = _escape_body(content)
        cmd = (
            f'am start -a android.intent.action.SENDTO -d sms:{phone} '
            f'--es sms_body "{body}" -p {sms_pkg}'
        )
        try:
            self.d.shell(cmd)
        except Exception as e:
            return ActionResult(self.channel, self.action, False, f"shell: {e!r}")

        time.sleep(1.5)

        # MIUI 兜底：若仍在会话列表，先点切到编辑器
        for sel in SWITCH_TO_EDITOR_SELECTORS:
            try:
                sw = self.d(**sel)
                if sw.exists:
                    sw.click()
                    time.sleep(0.8)
                    break
            except Exception:
                continue

        # 显式清空 + set_text —— 不信 sms_body extra，处理"已有会话/残留旧文本"情况
        for sel in EDIT_TEXT_SELECTORS:
            try:
                et = self.d(**sel)
                if et.wait(timeout=1.5):
                    et.clear_text()
                    et.set_text(content)
                    time.sleep(0.3)
                    break
            except Exception:
                continue

        if not auto_send:
            # 默认：停在 editor 预填正文，等老人按发送
            return ActionResult(
                self.channel, self.action, True,
                f"compose 打开并预填 (to={phone}, len={len(content)})；等老人按发送",
                payload={"phone": phone, "content": content, "auto_send": False},
            )

        # auto_send=True：demo 场景，脚本点发送
        clicked = False
        for sel in SEND_BTN_SELECTORS:
            try:
                btn = self.d(**sel)
                if btn.wait(timeout=1.5):
                    btn.click()
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            return ActionResult(
                self.channel, self.action, False,
                "compose 打开了但找不到发送按钮（扩 SEND_BTN_SELECTORS）",
                payload={"phone": phone, "content": content, "auto_send": True},
            )

        time.sleep(0.6)
        return ActionResult(
            self.channel, self.action, True,
            f"auto-sent to {phone} (len={len(content)})",
            payload={"phone": phone, "content": content, "auto_send": True},
        )

    def healthcheck(self) -> ActionResult:
        try:
            info = self.d.info
        except Exception as e:
            return ActionResult(self.channel, self.action, False, f"adb: {e!r}")
        return ActionResult(
            self.channel, self.action, True,
            f"device={info.get('productName')}",
        )

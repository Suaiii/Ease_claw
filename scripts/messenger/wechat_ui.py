"""WeChat UI 自动化适配器（uiautomator2 + LDPlayer）。

D4 已跑通。D5 遇微信风控，暂降级为 R&D 通道保留 —— 正式 demo 走 whatsapp / sms。
复用 scripts/wechat_send.py 的 open_chat_with + send_text 逻辑。
"""
from __future__ import annotations

import sys
from pathlib import Path

from .base import MessengerAdapter, SendResult

# 让 wechat_send 能被 import（它在 scripts/ 根下）
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


class WeChatUiAdapter(MessengerAdapter):
    channel = "wechat_ui"

    def __init__(self, device=None):
        import uiautomator2 as u2

        self.d = device or u2.connect()

    def send(self, to: str, msg: str) -> SendResult:
        from wechat_send import open_chat_with, send_text  # noqa: E402

        if not to:
            return SendResult(self.channel, False, "no contact specified")
        try:
            open_chat_with(self.d, to)
            send_text(self.d, msg)
        except Exception as e:
            return SendResult(self.channel, False, f"ui automation: {e!r}")
        return SendResult(self.channel, True, f"contact={to}")

    def healthcheck(self) -> SendResult:
        try:
            info = self.d.info
        except Exception as e:
            return SendResult(self.channel, False, f"adb: {e!r}")
        return SendResult(self.channel, True, f"device={info.get('productName')}")

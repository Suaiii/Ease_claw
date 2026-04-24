"""CallAdapter — 语音驱动拨号。

实现：uiautomator2 的 `d.shell('am start -a android.intent.action.DIAL -d tel:XXX')`。
DIAL（不是 CALL）只"打开拨号器 + 预填号码"，老人按绿键确认才真正拨出。
这避免了 Android 10+ 对 ACTION_CALL 权限的限制，也天然满足"代操作必须有用户确认"的授权约束。

params:
  phone: str    E.164 或本地号码；纯数字（不带 +/- / 空格）
"""
from __future__ import annotations

import re
from typing import Any

from .base import ActionAdapter, ActionResult


def _sanitize(phone: str) -> str:
    # tel: URI 容忍 +0-9，但我们直接剥所有非数字（模拟器 demo 场景没国际号）
    return re.sub(r"[^\d+]", "", phone or "")


class CallAdapter(ActionAdapter):
    channel = "call"
    action = "call"

    def __init__(self, device: Any = None):
        import uiautomator2 as u2

        self.d = device or u2.connect()

    def execute(self, params: dict) -> ActionResult:
        phone = _sanitize(params.get("phone", ""))
        if not phone:
            return ActionResult(self.channel, self.action, False, "no phone in params")
        cmd = f'am start -a android.intent.action.DIAL -d tel:{phone}'
        try:
            self.d.shell(cmd)
        except Exception as e:
            return ActionResult(self.channel, self.action, False, f"shell: {e!r}")
        return ActionResult(
            self.channel, self.action, True,
            f"dialer opened for {phone}（等老人按绿键接通）",
            payload={"phone": phone},
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

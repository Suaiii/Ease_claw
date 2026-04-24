"""ClawEase adapter 抽象基类。

两层：
- `ActionAdapter` 是通用动作适配器，按 `execute(params) -> ActionResult` 调用。
  C 方案后新建的 adapter（call / sms-intent / inbox）都走这一层。
- `MessengerAdapter` 是历史文本消息专用，保留以兼容 WhatsAppAdapter / SmsAliyunAdapter / WeChatUiAdapter。
  新代码请优先用 ActionAdapter。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionResult:
    channel: str
    action: str
    ok: bool
    detail: str = ""
    payload: Any = None


@dataclass
class SendResult:
    """历史文本消息结果（MessengerAdapter 专用）。"""
    channel: str
    ok: bool
    detail: str = ""


class ActionAdapter(ABC):
    channel: str = ""
    action: str = ""

    @abstractmethod
    def execute(self, params: dict) -> ActionResult:
        """按 params 执行一个动作。params 的字段由各 adapter 约定（phone / to / content / limit 等）。"""

    def healthcheck(self) -> ActionResult:
        """轻量检查运行前置（设备连通 / 凭证 / SDK 可用等）。默认 ok=True。"""
        return ActionResult(self.channel, self.action, True, "ok (default)")


class MessengerAdapter(ABC):
    """文本消息专用。向后兼容；新 adapter 走 ActionAdapter。"""
    channel: str = ""

    @abstractmethod
    def send(self, to: str, msg: str) -> SendResult:
        """发一条文本消息给 to。to 的格式由各 adapter 自己定（手机号 / 微信联系人名 / wxid）。"""

    @abstractmethod
    def healthcheck(self) -> SendResult:
        """轻量检查凭证 / 连通性。ok=True 表示现在能发。"""

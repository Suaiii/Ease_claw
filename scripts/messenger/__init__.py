"""ClawEase MessengerAdapter 包。

用法：
    from messenger.whatsapp import WhatsAppAdapter
    from messenger.sms import SmsAdapter
    from messenger.wechat_ui import WeChatUiAdapter

所有 adapter 实现 `MessengerAdapter.send(to, msg) -> SendResult`。
凭证统一从环境变量读取（或构造参数覆盖），env 由 voice_to_messenger.py 从 .env 装载。
"""
from .base import ActionAdapter, ActionResult, MessengerAdapter, SendResult

__all__ = ["ActionAdapter", "ActionResult", "MessengerAdapter", "SendResult"]

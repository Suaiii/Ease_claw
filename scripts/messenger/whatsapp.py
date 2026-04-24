"""WhatsApp Cloud API 适配器。

参考：https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
免费 sandbox：Meta 送一个 test phone number + 最多 5 个预注册 recipient。
"""
from __future__ import annotations

import os

import requests

from .base import MessengerAdapter, SendResult


class WhatsAppAdapter(MessengerAdapter):
    channel = "whatsapp"

    def __init__(
        self,
        phone_number_id: str | None = None,
        access_token: str | None = None,
        default_recipient: str | None = None,
        api_version: str = "v21.0",
    ):
        self.phone_number_id = phone_number_id or os.environ.get("WA_PHONE_NUMBER_ID", "")
        self.access_token = access_token or os.environ.get("WA_ACCESS_TOKEN", "")
        self.default_recipient = default_recipient or os.environ.get("WA_RECIPIENT", "")
        self.api_version = api_version
        if not self.phone_number_id or not self.access_token:
            raise RuntimeError(
                "WhatsApp 凭证缺失。需要 WA_PHONE_NUMBER_ID + WA_ACCESS_TOKEN（.env 或构造参数）"
            )

    @property
    def _endpoint(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def send(self, to: str, msg: str) -> SendResult:
        recipient = to or self.default_recipient
        if not recipient:
            return SendResult(self.channel, False, "no recipient specified")
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"body": msg},
        }
        try:
            r = requests.post(self._endpoint, headers=self._headers, json=payload, timeout=30)
        except Exception as e:
            return SendResult(self.channel, False, f"network: {e!r}")
        if r.status_code >= 400:
            return SendResult(self.channel, False, f"http {r.status_code}: {r.text[:500]}")
        msg_id = (r.json().get("messages") or [{}])[0].get("id", "")
        return SendResult(self.channel, True, f"wa_msg_id={msg_id}")

    def healthcheck(self) -> SendResult:
        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
        try:
            r = requests.get(url, headers=self._headers, timeout=10)
        except Exception as e:
            return SendResult(self.channel, False, f"network: {e!r}")
        if r.status_code >= 400:
            return SendResult(self.channel, False, f"http {r.status_code}: {r.text[:200]}")
        return SendResult(self.channel, True, "cloud api reachable")

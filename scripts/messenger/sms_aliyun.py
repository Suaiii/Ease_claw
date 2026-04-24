"""阿里云短信适配器（dysmsapi 2017-05-25）—— B 方案遗留，远程兜底用。

C 方案 Layer 1 走 Android intent 驱动的 SmsAdapter（见 sms.py）。
这份保留用于：
  - 没有手机 / 模拟器可控时的远程短信通道
  - 未来做"亲属 web 控制台代发短信"的后端
pip 依赖（延迟 import）：alibabacloud-dysmsapi20170525, alibabacloud-tea-openapi
模板变量固定叫 `content`，对应模板样式 `【签名】${content}`。
"""
from __future__ import annotations

import json
import os

from .base import MessengerAdapter, SendResult


class SmsAliyunAdapter(MessengerAdapter):
    channel = "sms_aliyun"

    def __init__(
        self,
        access_key_id: str | None = None,
        access_key_secret: str | None = None,
        sign_name: str | None = None,
        template_code: str | None = None,
        default_recipient: str | None = None,
        region: str = "cn-hangzhou",
    ):
        self.access_key_id = access_key_id or os.environ.get("ALIYUN_AK_ID", "")
        self.access_key_secret = access_key_secret or os.environ.get("ALIYUN_AK_SECRET", "")
        self.sign_name = sign_name or os.environ.get("ALIYUN_SMS_SIGN", "")
        self.template_code = template_code or os.environ.get("ALIYUN_SMS_TEMPLATE", "")
        self.default_recipient = default_recipient or os.environ.get("SMS_RECIPIENT", "")
        self.region = region
        missing = [
            k
            for k, v in {
                "ALIYUN_AK_ID": self.access_key_id,
                "ALIYUN_AK_SECRET": self.access_key_secret,
                "ALIYUN_SMS_SIGN": self.sign_name,
                "ALIYUN_SMS_TEMPLATE": self.template_code,
            }.items()
            if not v
        ]
        if missing:
            raise RuntimeError(f"阿里云短信凭证缺失：{missing}")
        self._client = None

    def _get_client(self):
        if self._client is None:
            from alibabacloud_dysmsapi20170525.client import Client
            from alibabacloud_tea_openapi import models as open_api_models

            config = open_api_models.Config(
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret,
            )
            config.endpoint = f"dysmsapi.{self.region}.aliyuncs.com"
            self._client = Client(config)
        return self._client

    def send(self, to: str, msg: str) -> SendResult:
        recipient = to or self.default_recipient
        if not recipient:
            return SendResult(self.channel, False, "no recipient specified")
        try:
            from alibabacloud_dysmsapi20170525 import models as dysmsapi_models
        except ImportError:
            return SendResult(
                self.channel,
                False,
                "缺 SDK：pip install alibabacloud-dysmsapi20170525 alibabacloud-tea-openapi",
            )
        client = self._get_client()
        req = dysmsapi_models.SendSmsRequest(
            phone_numbers=recipient,
            sign_name=self.sign_name,
            template_code=self.template_code,
            template_param=json.dumps({"content": msg}, ensure_ascii=False),
        )
        try:
            resp = client.send_sms(req)
        except Exception as e:
            return SendResult(self.channel, False, f"sdk: {e!r}")
        body = resp.body
        if body.code != "OK":
            return SendResult(self.channel, False, f"{body.code}: {body.message}")
        return SendResult(self.channel, True, f"biz_id={body.biz_id}")

    def healthcheck(self) -> SendResult:
        try:
            self._get_client()
        except Exception as e:
            return SendResult(self.channel, False, f"sdk init: {e!r}")
        return SendResult(self.channel, True, "aliyun sdk initialized")

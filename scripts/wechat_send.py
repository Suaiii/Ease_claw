"""
ClawEase — D4 demo: 在模拟器微信里给指定联系人发一条文本消息。
依赖：uiautomator2, adbutils（在 E:\\aNB\\Ease-claw\\.conda\\clawease 里）
运行：
  E:\\aNB\\Ease-claw\\.conda\\clawease\\python.exe E:\\aNB\\Ease-claw\\scripts\\wechat_send.py --to "联系人名" --msg "你好"

前置：微信已登录，至少加了目标联系人为好友。
"""
from __future__ import annotations

import argparse
import sys
import time

import uiautomator2 as u2

WECHAT_PKG = "com.tencent.mm"


LOGIN_ACTIVITY_MARKERS = ("LoginPasswordUI", "MobileInputUI", "LoginHistoryUI", "SmsLoginUI")


def ensure_wechat_foreground(d: u2.Device) -> None:
    current = d.app_current()
    if current.get("package") != WECHAT_PKG:
        d.app_start(WECHAT_PKG, stop=False)
        time.sleep(2.0)
        current = d.app_current()
    activity = current.get("activity", "")
    if any(m in activity for m in LOGIN_ACTIVITY_MARKERS):
        raise RuntimeError(
            f"微信处于登录页 ({activity})。模拟器常被风控踢下线，"
            f"请在手机上重新登录（短信验证码），登录后进入聊天列表再重试。"
        )


def open_chat_with(d: u2.Device, contact: str) -> None:
    # 回到微信首页。用 back 把可能的搜索页/子页清掉，再点 "微信" tab。
    ensure_wechat_foreground(d)
    for _ in range(3):
        if d.app_current().get("activity", "").endswith("LauncherUI"):
            break
        d.press("back")
        time.sleep(0.4)
    d(text="微信").click_exists(timeout=3)
    time.sleep(0.6)

    # 直接从聊天列表里点联系人行。如果不在可视区，uiautomator2 会自动滚动查找。
    row = d(text=contact)
    if not row.wait(timeout=3):
        row.scroll.to(text=contact)
    if not row.exists:
        raise RuntimeError(f"聊天列表里找不到 {contact!r}（需要先在手机上给 TA 发一次消息以进列表）")
    row.click()
    time.sleep(1.0)


def send_text(d: u2.Device, text: str) -> None:
    # 输入框。新版微信输入框 resource-id 通常是 com.tencent.mm:id/input 或类似
    # 先用 className=EditText 兜底
    input_box = d(className="android.widget.EditText")
    if not input_box.wait(timeout=5):
        raise RuntimeError("找不到聊天输入框")
    input_box.set_text(text)
    time.sleep(0.3)
    # 发送按钮（通常 text="发送"）
    if not d(text="发送").click_exists(timeout=3):
        raise RuntimeError("找不到发送按钮（可能键盘没收起 / 联系人未打开）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True, help="微信联系人姓名（备注名或昵称）")
    ap.add_argument("--msg", required=True, help="要发送的文本")
    ap.add_argument("--screenshot", help="可选：发送后截一张屏保存到路径")
    args = ap.parse_args()

    d = u2.connect()  # 默认连 adb devices 里的第一个
    print(f"[clawease] connected: {d.info.get('productName')}  size={d.window_size()}")

    open_chat_with(d, args.to)
    send_text(d, args.msg)
    print(f"[clawease] sent to {args.to!r}: {args.msg!r}")

    if args.screenshot:
        time.sleep(0.8)
        d.screenshot(args.screenshot)
        print(f"[clawease] screenshot -> {args.screenshot}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

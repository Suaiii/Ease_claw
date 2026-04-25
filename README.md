# ClawEase

语音驱动的老人 / 视障无障碍代理。一句中文命令 → 打电话、发短信、读带反诈标注的收件箱。

基于 [OpenClaw](https://github.com/OpenClaw/openclaw) 做意图解析；adb / uiautomator2 落到真机 Android。SJTU OpenClaw 大赛创意赛道作品。

## 它做什么

老人对着浏览器说一句中文，比如"给 10086 打电话"、"有没有新短信"、"给 12306 发一条我晚点到"，系统：

1. 浏览器 `webkitSpeechRecognition` 把语音转中文文本
2. OpenClaw（Gemini 2.5 Flash）zero-shot 解析成 `{action, target, content}`
3. 路由到三个 ActionAdapter 之一执行：
   - `call` → `am start ACTION_DIAL` 弹拨号器，老人按绿键确认
   - `send_sms` → `am start ACTION_SENDTO` 预填短信，停在编辑器等老人按发送
   - `read_inbox` → `adb shell content query content://sms/inbox` 拉收件箱
4. 收件箱每条短信走 5 类反诈分类，验证码自动加"不要告诉任何人"前缀朗读

设计上的两条硬约束：

- **不替老人按发送 / 接听** —— DIAL 不 CALL、短信停在编辑器，每次代操作都有物理授权
- **不删不屏蔽诈骗短信** —— 只做朗读标注，老人保留对原始信息的访问权

## 反诈 5 类

| 分类 | 朗读前缀 |
|---|---|
| 正常 | 无 |
| 验证码 | **「警告：这是验证码短信，不要告诉任何人」** |
| 话费订单 | 「话费通知」 |
| 冒充银行 / 冒充公检法 / 快递通知 | 「可疑：疑似 X 诈骗，请谨慎」 |

LLM 不可用时 regex 兜底至少识别验证码模式。

## 跑起来

需求：Windows 11 + Python 3.11 + Node.js（OpenClaw 用 pnpm）+ 一台 Android 设备（USB 调试打开）。

```powershell
# 1. 启动本地 demo 服务
./start_demo.ps1

# 2. 浏览器打开
# http://127.0.0.1:8765
```

页面有三个视图：

- `/` —— 双端 shell，左老人端 + 右操作员控制台
- `/?view=elder` —— 老人端大字视图，麦克风 + 三张大命令卡
- `/?view=operator` —— 操作员控制台，意图解析 / 设备状态 / 执行轨迹

支持中-英语言切换（右上角药丸切换器，跨 iframe 同步）。

## 工程结构

```
demo/                      # 三视图前端（zero-build，原生 HTML/CSS/JS）
  index.html               # dual-view shell（iframe 老人端 + 控制台）
  elder.html               # 老人端
  operator.html            # 操作员控制台
  i18n.js                  # 共享中-英语言切换工具

scripts/
  demo_server.py           # 本地 HTTP 服务（127.0.0.1:8765）
  voice_to_action.py       # 编排入口，按 action 路由
  spam_categories.py       # 5 类反诈分类 + 朗读前缀
  tts_local.py             # 本地 TTS（pyttsx3 / SAPI）
  messenger/
    base.py                # ActionAdapter ABC
    call.py                # CallAdapter（ACTION_DIAL）
    sms.py                 # SmsAdapter（ACTION_SENDTO + uiautomator2 点发送）
    inbox.py               # InboxReaderAdapter（content query）

contacts.json              # 联系人路由表 name → {phone, note}
notes/
  ARCHITECTURE.md          # 架构详解
  CHANGELOG.md             # 单兵作战进展记录
```

## 当前状态

Layer 1（Python + adb + OpenClaw）已在小米 13（MIUI）真机 smoke 通过：

- CallAdapter / SmsAdapter / InboxReaderAdapter 三件套全绿
- 浏览器 ASR 接入 textarea，麦克风按钮按一下开始录
- 反诈 5 类 zero-shot 分类，offline regex 兜底验证码
- 三视图 demo 站点支持中-英切换

下一步走 Kotlin 原生 APK，Intent + ContentResolver 路径，不依赖无障碍服务、不 root。

详见 [`notes/ARCHITECTURE.md`](notes/ARCHITECTURE.md) 和 [`notes/CHANGELOG.md`](notes/CHANGELOG.md)。

## 许可

待补。

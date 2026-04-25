# ClawEase

语音驱动的老人 / 视障无障碍代理。一句中文命令 → 打电话、发短信、读带反诈标注的收件箱。

当前主链基于云端 [OpenClaw](https://github.com/OpenClaw/openclaw) 做秒级意图解析；本地 Python adapter 通过 `adb` / Android `intent` 落到真机执行。SJTU OpenClaw 大赛创意赛道作品。

## 它做什么

老人对着浏览器说一句中文，比如"给 10086 打电话"、"有没有新短信"、"给 12306 发一条我晚点到"，系统：

1. 浏览器 `webkitSpeechRecognition` 把语音转中文文本
2. 云端 OpenClaw 把命令解析成 `{action, target, content}`
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

## 固定启动方式

需求：Windows 11 + 项目内 `.conda\clawease` Python + Node.js + 一台 Android 设备（USB 调试打开，可选但真机动作需要）。

### 1. 启动当前产品栈

```powershell
./start_product.ps1
```

这个入口会做两件事：

1. 启动并校验云端 OpenClaw relay
2. 启动本地 demo 服务 `http://127.0.0.1:8765`

### 2. 直接调用当前主链

```powershell
E:\aNB\Ease-claw\.conda\clawease\python.exe E:\aNB\Ease-claw\scripts\voice_to_action.py --voice-text "给10086打电话"
E:\aNB\Ease-claw\.conda\clawease\python.exe E:\aNB\Ease-claw\scripts\voice_to_action.py --voice-text "给12306发一条我晚点到"
E:\aNB\Ease-claw\.conda\clawease\python.exe E:\aNB\Ease-claw\scripts\voice_to_action.py --voice-text "有没有新短信" --no-tts
```

### 3. 停止云端 relay

```powershell
./stop_product.ps1
```

说明：

- 当前默认解析模式是 `OPENCLAW_PARSE_MODE=openclaw_cloud`
- 项目使用专用云端 state：`E:\aNB\Ease-claw\.openclaw-cloud`
- 业务脚本不直接暴露远端公网 WS，而是固定经由本机 `127.0.0.1:31879` relay

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

当前成立的是一条云端语义 + 本地执行的产品主链：

- 云端 OpenClaw 已接入业务链，意图解析可稳定到秒级
- `voice_to_action.py` 默认通过云端 OpenClaw 返回结构化动作
- CallAdapter / SmsAdapter / InboxReaderAdapter 三件套可执行真机动作
- 浏览器 ASR 接入 textarea，麦克风按钮按一下开始录
- 反诈 5 类分类可用，offline regex 兜底验证码
- 三视图 demo 站点支持中英切换

当前还没有完全做到的是：

- OpenClaw 还不是手机原生执行层，手机动作仍由 Python adapter 落地
- 标准 OpenClaw CLI 的远端 metadata-change 审批流还未完全收口
- 真机端到端仍依赖 `adb` 与设备状态稳定

下一步目标仍然是把手机动作进一步封成 OpenClaw 工具，而不是停留在“模型解析 + Python 执行”。

详见 [`notes/ARCHITECTURE.md`](notes/ARCHITECTURE.md) 和 [`notes/CHANGELOG.md`](notes/CHANGELOG.md)。

## 许可

待补。

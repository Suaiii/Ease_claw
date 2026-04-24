# ClawEase — 架构（Layer 1 / C 方案）

> 一句话：**语音驱动的通讯层代理** —— 老人/视障用户用一句中文命令完成「打电话 / 发短信 / 读带反诈标注的收件箱」。

---

## 1. 链路图

```
        ┌─────────────────────┐
        │  老人说一句中文     │   例："有没有新短信" / "给女儿打电话"
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │  OpenClaw 意图解析  │   Gemini zero-shot → {action, target, content}
        │  (ASR 层 Layer 2)   │   action ∈ {call, send_sms, read_inbox}
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │  voice_to_action.py │   按 action 路由；用 contacts.json 解析联系人→手机号
        └──┬──────┬───────┬───┘
           │      │       │
           ▼      ▼       ▼
    ┌──────┐ ┌───────┐ ┌──────────────┐
    │Call  │ │ Sms   │ │InboxReader   │
    │Adapt │ │Adapter│ │Adapter       │
    └──┬───┘ └───┬───┘ └──────┬───────┘
       │         │            │
       │         │            ├──► content query (content://sms/inbox)
       │         │            ├──► spam_categories.classify_sms (LLM)
       │         │            └──► tts_local.speak(【警告/可疑】前缀 + 正文)
       │         │
       ▼         ▼
    am start  am start
    ACTION_   ACTION_     ← 全部通过 adb / uiautomator2 落到 Android
    DIAL      SENDTO
                +
            uiautomator2
            点"发送"
```

---

## 2. 核心抽象

### `ActionAdapter`（`scripts/messenger/base.py`）
```python
class ActionAdapter(ABC):
    channel: str
    action:  str
    @abstractmethod
    def execute(self, params: dict) -> ActionResult: ...
    def healthcheck(self) -> ActionResult: ...
```

三个 Layer 1 实现：

| Adapter | action | 机制 | 关键点 |
|---|---|---|---|
| `CallAdapter` | `call` | `am start ACTION_DIAL tel:XXX` | DIAL 不 CALL → 老人按绿键确认 = 自然授权，绕 Android 10+ CALL_PHONE 权限 |
| `SmsAdapter` | `send_sms` | `am start ACTION_SENDTO sms:XXX + --es sms_body` + uiautomator2 点"发送" | 跨 ROM selector 多条兜底 |
| `InboxReaderAdapter` | `read_inbox` | `adb shell content query content://sms/inbox` | 纯数据读取，不靠 UI dump；每条喂 `spam_categories.classify_sms` |

---

## 3. 反诈 5 类（`scripts/spam_categories.py`）

1. **冒充银行**  假装 ICBC/BOC/CCB 等，要点链接/回电/转账
2. **冒充公检法**  假装警察/法院/社保局要求配合调查
3. **中奖**  声称中奖/抽中奖品要求领取
4. **快递通知**  假装快递丢失/海关扣留要求操作
5. **验证码**  含 4-8 位数字验证码 → 老人社工诈骗的**头号入口**

**朗读前缀规则**（不删不屏蔽，只做标注）：
- `正常` → 无前缀
- `验证码` → **「警告：这是验证码短信，不要告诉任何人」**
- 其他 4 类 → **「可疑：疑似 X 诈骗，请谨慎」**

LLM 不可用时 regex 兜底至少识别验证码模式。

---

## 4. 可替换性 / 演进口子

- **IM 平台中立**：`MessengerAdapter` 抽象层仍保留 WhatsApp / 阿里云 SMS / 微信 UI 三个 adapter 作**远程兜底 + R&D**。要换平台只加一个 adapter。
- **模型中立**：意图 prompt 和反诈 prompt 都走 `call_openclaw` 注入，不硬编码 provider。Layer 2 切百炼 / Kimi / GLM 只改路由层。
- **TTS 中立**：`tts_local.py` 首选 pyttsx3、兜底 SAPI，Layer 2 换流式 / 云端 TTS 只换一个文件。
- **全局化 UI 口子**：Layer 1 脚本化运行；Layer 2 可选做系统级无障碍服务 app，同样的 ActionAdapter 层直接复用。

---

## 5. 伦理与授权硬约束（已融入 Layer 1）

- **每次拨号都有老人按键确认**（DIAL 而非 CALL）→ 天然满足"代操作必须有监护人授权日志"原则
- **短信仅预填 + 自动点发送**，正文在屏幕上可见 → 便于老人反悔
- **读收件箱不自动删、不屏蔽**，只做朗读标注 → 老人保留对原始信息的访问权
- **验证码警告由 skill 自动播报**，默认前缀"不要告诉任何人" → 安全底线内建

---

## 6. 未来路径（不在 Layer 1）

- Layer 2：ASR 双校（Paraformer + SenseVoice + LLM 纠错）、方言识别 ≥ 85%
- Layer 3：视障无障碍合规（WAI-ARIA + TalkBack/VoiceOver 测试）
- Layer 3：反诈话术库 → 7B 小模型初筛 + 大模型终判 + 国家反诈中心 API 兜底

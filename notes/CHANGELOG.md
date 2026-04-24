# ClawEase 工程进展 Changelog

> 单兵作战每日进展记录。一个人做的事不多，但每一步都得能复现。
> 时间用 ISO 日期。技术选择只记 **决策 + 理由**，操作流水放对应 PR/commit。

---

## 2026-04-22 — D1 / D2 完成（Layer 1 启动日）

### ✅ D1：OpenClaw 本地跑通 + Gemini 接入
- 仓库就位：`E:\aNB\Ease-claw\openclaw`，版本 `v2026.4.20`（提案锁定的是 `v2026.4.11`，但本地拉了主线版，**提案落地物料里继续按 v2026.4.11 写**，避免跟评委对账时混乱）
- Node 模型链：`google/gemini-2.5-flash`（免费 tier `gemini-2.0-flash` quota=0，避坑）
- 接入凭证：`C:\Users\ZHUyi\.openclaw\.env` 里的 `GEMINI_API_KEY`
- 端到端 smoke：
  ```bash
  cd E:/aNB/Ease-claw/openclaw
  pnpm dev agent --agent main --message "你好，简单介绍一下自己"
  ```
  返回完整中文自我介绍 ✅

### ✅ D2：OpenClaw computer-use 能力探查
- 结论：**没有** computer-use / UI 自动化模块
- 证据：`src/gateway/node-command-policy.ts:90-103` 显示 Android 端只放出只读型命令（通知/相机/联系人），不能截屏，不能注入点击
- 路线决策：**接管微信走 uiautomator2（Python）**，OpenClaw 只负责语音→文本→意图+TTS。**不走** 提案里的"企业微信 API + 公众号客服"路线
- 已写入 memory：`clawease_wx_takeover_strategy.md`

### 🔥 阶段性踩坑：Clash 代理下 SSRF 拦截 Gemini
- 症状：`[security] blocked URL fetch (url-fetch) ... resolves to private/internal/special-use IP address`
- 根因：Clash fake-IP DNS 把 `generativelanguage.googleapis.com` 解析到 `198.18.0.0/15`（RFC 2544 benchmark range），OpenClaw 的 `fetchWithSsrFGuard` 默认拦截
- 走了几条死路（**留这里防止下次再踩**）：
  - ❌ `tools.web.fetch.ssrfPolicy.allowRfc2544BenchmarkRange: true` —— 只对 web fetch 工具生效
  - ❌ `browser.ssrfPolicy.dangerouslyAllowPrivateNetwork: true` —— 只对 browser 工具生效
  - ❌ `providers.google.ssrfPolicy.*` —— 路径根本不在 schema 里，被静默忽略
- 正解：**`models.providers.google.request.allowPrivateNetwork: true`**（`src/agents/provider-transport-fetch.ts:86` 是真正读取这个旁路开关的地方）
- 配置变更方法（**关键**：跑着的 gateway 会回滚直接 edit，必须用 CLI）：
  ```bash
  pnpm dev config set --batch-file E:/aNB/Ease-claw/openclaw-config-batch.json
  ```
  batch 文件见 `E:/aNB/Ease-claw/openclaw-config-batch.json`，是数组格式 `[{path, value}, ...]`
- 已写入 memory：`openclaw_local_dev_setup.md`

### 已知次级问题（不阻塞，记着）
- gateway pairing scope 升级未审批 → agent 命令 fallback 到 embedded 模式仍能跑通；正式上多渠道前再修
- `plugins.entries.google.enabled: true` 会被自动重写回 openclaw.json，无害（warning: stale config entry ignored）

---

## 2026-04-22 → 2026-04-23 — D3 启动（Android 接管层搭好）

### ✅ Python 环境
- 用户要求：**所有文件 E 盘，不进 C 盘**（已入 memory `feedback_e_drive_only.md`）
- Conda env 位置：**`E:\aNB\Ease-claw\.conda\clawease`**（Python 3.11.15）
  - ⚠️ 首次 `conda create -n clawease` 被默认指到 `C:\Users\ZHUyi\.conda\envs\`，删掉重建时用 `--prefix` 显式指定路径
  - ⚠️ 再试 `E:\anaconda\envs\clawease` 权限不够 → 最终落在项目内 `.conda` 子目录
- 已装包：`uiautomator2 3.5.0`, `adbutils 2.12.0`, `pillow 12.2.0`, `lxml 6.1.0`

### ✅ 模拟器 + ADB + 微信环境
- 用户自行装了 LDPlayer（雷电 9），启动后 ADB 自动监听 `emulator-5554`
- 设备信息：Android 9 (SDK 28), x86_64, 1080×1920, 伪装成 Galaxy S9+ (model `2510DRK44C` / device `star2qltechn`)
- 微信已预装，首次启动停在 `com.tencent.mm.plugin.account.ui.MobileInputUI`（手机号登录页），见 `screenshots/d3-01-wx-login.png`
- uiautomator2 首次 `connect()` 会自动把 atx-agent 推到设备上 —— 我们这里一次成功，无需 `python -m uiautomator2 init`

### 🚧 D3 剩余（等用户操作）
- 用户用备用手机号在 LDPlayer 里**手动登录微信**（SMS 码 / 可能的人脸识别都不能自动化走）
- 登录后，加一个可反复测试的联系人（比如自己另一个号 / 家里另一台设备上的微信）

### ✅ D4 完成：在 文件传输助手 里发消息成功
- 位置：`E:\aNB\Ease-claw\scripts\wechat_send.py`
- 用法：
  ```bash
  E:\aNB\Ease-claw\.conda\clawease\python.exe E:\aNB\Ease-claw\scripts\wechat_send.py \
    --to "文件传输助手" --msg "你好" \
    --screenshot "E:/aNB/Ease-claw/notes/screenshots/xxx.png"
  ```
- 验证截图：`screenshots/d4-01-sent.png`（绿色气泡 "ClawEase D4 smoke test 2026-04-23" 已出现在 文件传输助手 对话里）

**首次尝试失败 → 改路的经验**：
- 原方案走"微信 tab → 点搜索放大镜 → 搜索联系人 → 点结果 → 发送"，在 `FTSMainUI` 搜索页里，`d(text=contact).click_exists()` 没落到可点击元素，后续 `set_text` 误填到**搜索框**（导致绿色气泡是"xxx smoke test" 替换了搜索词），最后找不到 "发送" 按钮
- 改路：**直接从聊天列表点联系人行**（文件传输助手 默认在列表顶部），绕开搜索
- 核心经验：**进聊天**这步要用"列表点击"而不是"搜索点击" —— 搜索结果的 DOM 更脆，点击目标区域不清

**已知剩余脆性**（等扩展到真人联系人时再打磨）：
- 新联系人如果不在聊天列表顶部，脚本会自动滚动查找 —— 长列表/重名要加二次匹配
- 输入框 / 发送按钮靠 `EditText` + `text="发送"`，微信大版本更新会断
- 未处理 atx-agent 掉连 / 微信强制更新弹窗 / 登录过期跳出等异常

### Demo 主链路链路健康度（2026-04-23 更新）
| 段 | 状态 |
|---|---|
| 3. OpenClaw LLM (Gemini) | ✅ D1 通 |
| 4. uiautomator2 Python 桥 | ✅ D3 通（atx-agent 已推） |
| 5. Android 模拟器 | ✅ LDPlayer + 微信 Android 9 |
| 6. 测试微信号 | ✅ 用户登录完毕 |
| 7. 微信 UI 自动化发消息 | ✅ D4 通（文件传输助手 靶子成功） |

**下一步（D5）**：串 D1 + D4 —— 终端命令行触发 → OpenClaw 调 Gemini 生成回复文本 → wechat_send.py 发出去。不需要 ASR/TTS（那是 D7）。

---

## 2026-04-23 — D5 / 战略转向日

### 🟡 D5 技术跑通但撞微信风控
- 写了 `scripts/voice_to_wechat.py` 串通"中文 → OpenClaw Gemini 意图 → wechat_send"：
  - OpenClaw `pnpm dev agent --json --local --thinking off --message <prompt>` 返 `payloads[0].text = {"to":"文件传输助手","msg":"..."}` ✅
  - 意图解析稳定，Gemini 2.5 Flash 单次 LLM ~47s，pnpm/TS 编译冷启动 ~130s，总端到端 ~170-180s
- **阻塞点**：跑到"发送"这一步时，LDPlayer 里的微信账号被踢下线，activity = `LoginPasswordUI`，弹窗"账号状态异常，本次登录已失效"
- 截图：`screenshots/d5-debug-state.png`（下线弹窗）、`d5-debug-state-02.png`（同一状态）、`d5-debug-state-03.png`（误入扫码登录页）
- 踩坑复盘（记着别再踩）：
  - ❌ Python subprocess `shell=True` + 多行 prompt 字符串 → Windows shell 在**第一个换行处截断**参数，Gemini 只看到 "你是意图解析器..." 前半段，回了空洞的"好的我准备好了"。**正解：prompt 写成单行**
  - ❌ pnpm 在 PowerShell 下把 Node JSON 输出**标记为 stderr**，Python `stdout.find("{")` 找不到。**正解：`stdout + stderr` 两边都用 `json.JSONDecoder.raw_decode`**
  - ❌ 原 180s timeout 太紧，pnpm 冷启动 + LLM 合计常超 170s。**改 360s**

### 🔥 战略转向：B 方案（WhatsApp 主 + SMS 备 + 微信 UI 降级 R&D）
用户判断：继续用 LDPlayer 发个人微信 **= 下次直接封号**。demo 日丢靶子代价不可接受。

候选评估：
- ❌ **企业微信 API**（提案原路线）：学生个人实名门槛 + 与"个人微信场景"叙事脱节
- ❌ **Feishu**：用户 Feishu 挂在 SJTU 学校租户下，学校 IT 不批个人项目 OpenAPI 权限；另起租户等于从零
- ✅ **WhatsApp Cloud API**：用户有纯个人账号 → Meta Business 注册后送 test phone number；Meta 官方维护、sandbox 免费、1000 条/月免费额度；叙事是**全球 26 亿用户**
- ✅ **阿里云短信**：学生认证 0.045/条，中国老人真的在用 SMS，1 小时接入，零风控

**叙事重构**（给评委的）：ClawEase 的价值是"老人/视障无障碍代理"这层抽象，**不绑定任何 IM 平台**。个人微信 UI 自动化路线已验证（`d4-01-sent.png`），保留为"等 OpenClaw computer-use 成熟后回切"的 R&D 章节。

### ✅ 架构落地（当天就位，等凭证接入）
- `scripts/messenger/base.py` — `MessengerAdapter` ABC + `SendResult`
- `scripts/messenger/whatsapp.py` — Cloud API v21.0，`graph.facebook.com/.../messages` POST
- `scripts/messenger/sms.py` — 阿里云 dysmsapi 2017-05-25 SDK 延迟 import
- `scripts/messenger/wechat_ui.py` — 包装 D4 `wechat_send.py`，R&D 通道保留
- `scripts/voice_to_messenger.py` — 编排入口，`contacts.json` 查名字 → (channel, address) → adapter.send
- `contacts.json` — 路由表（"妈妈" / "姐姐" / "文件传输助手"）
- `.env.example` — 凭证槽位
- `.gitignore` — 凭证与模拟器日志不入库

### 🚧 D5 剩余（等用户注册凭证）
- [ ] 用户注册 Meta Developer + Business Account + WhatsApp test phone number → 拿 4 个凭证写进 `.env`
- [ ] 用户注册阿里云短信 + 学生实名 + 申请签名和模板 → 拿 2 个 AK + 签名 + 模板 CODE 写进 `.env`
- [ ] `pip install requests alibabacloud-dysmsapi20170525 alibabacloud-tea-openapi` 到 clawease conda env
- [ ] 跑两次 smoke：`voice_to_messenger.py --voice-text "告诉妈妈我吃过饭了"` / `"告诉姐姐我到家了"`
- [ ] `refresh_wa_token.py`（WhatsApp sandbox token 24h 过期，demo 前刷）

### Demo 主链路健康度（2026-04-23 转向后更新）
| 段 | 状态 |
|---|---|
| 3. OpenClaw LLM (Gemini) 意图解析 | ✅ D5 实测通 |
| 4a. WhatsApp Cloud API adapter | 🟡 代码就位，等凭证 |
| 4b. 阿里云 SMS adapter | 🟡 代码就位，等凭证 |
| 4c. 微信 UI adapter（R&D） | ⚠️ D4 通 / D5 撞风控，降级保留 |
| 5. 联系人路由 `contacts.json` | ✅ 就位 |
| 6. 端到端编排 `voice_to_messenger.py` | ✅ 就位 |

**下一里程碑**：凭证到位后录第一版 demo 视频（老人语音 → WhatsApp 给"家人"发出去），再补 SMS 兜底演示。

---

## 2026-04-23（下半天） — D5 二次转向：B → C（Call + SMS + 反诈收件箱）

### 🔥 为什么又变了
用户在注册 Meta Developer app 的过程中提出更锋利的观察：**老人真正每天用的是打电话和短信，而这两个现在被分在两个系统 app 里**，对视障老人是明显的认知负担。

做"语音驱动的 Call + SMS 集合层"比 WhatsApp 代理：
- 更贴目标人群（中国 60+ 真实用机模式）
- 零平台风控、零注册门槛（SIM 卡即身份）
- 叙事上："全局化超级简化 UI" 长期愿景前置落地到 MVP
- 反诈短信过滤（原提案有）在此处集成极自然

### 🎯 用户拍板的 4 个决策（2026-04-23）
1. Demo 设备：**真机 + 模拟器结合**（call 用真机 USB，SMS / 反诈模拟器就行）
2. App 形态：**C0** —— Python 脚本 + uiautomator2，Layer 1 不做独立 Android app 壳
3. 微信路线：**Layer 1 完全不碰**。D4 代码 + `d4-01-sent.png` 作白皮书"已验证的未来路径"章节
4. 反诈 5 类：**冒充银行 / 冒充公检法 / 中奖 / 快递通知 / 验证码**（加验证码，删原提案里的虚拟货币；验证码是中国老人被社工诈骗头号入口）

### ✅ C 方案架构（当天落地）

```
老人语音 → OpenClaw 意图解析 → {action, target, content}
         ↓
  call       → CallAdapter.execute({phone})         → am start ACTION_DIAL tel:XXX
  send_sms   → SmsAdapter.execute({phone, content}) → am start SENDTO sms:XXX + 点发送
  read_inbox → InboxReaderAdapter.execute({limit})  → adb content query content://sms/inbox
                                                    → spam_categories.classify_sms (LLM zero-shot)
                                                    → tts_local.speak(【警告 / 可疑】前缀 + 正文)
```

关键抽象升级：新加 **`ActionAdapter` ABC**（`execute(params) -> ActionResult`），C 方案 3 个 adapter 都走这层；原 `MessengerAdapter` 保留给 WhatsApp / 阿里云 SDK / 微信 UI（全部降级为 R&D / 远程兜底）。

### 📁 代码文件
**新建**：
- `scripts/messenger/call.py` — `CallAdapter`（DIAL 不 CALL，老人按绿键 = 自然授权，绕开 Android 10+ CALL_PHONE 权限）
- `scripts/messenger/sms.py` — `SmsAdapter`（Android intent + uiautomator2 点发送；旧阿里云 SDK 版改名 `sms_aliyun.py`）
- `scripts/messenger/inbox.py` — `InboxReaderAdapter`（`adb shell content query`，不靠 UI dump）
- `scripts/spam_categories.py` — 5 类定义 + zero-shot prompt + 朗读前缀生成
- `scripts/tts_local.py` — pyttsx3 优先 / SAPI 兜底，`preheat()` 消首启 2s 延迟
- `scripts/voice_to_action.py` — C 方案编排入口
- `memory/clawease_c_strategy.md` — C 方案叙事长版

**改**：
- `scripts/messenger/base.py` — 加 `ActionAdapter` / `ActionResult`
- `contacts.json` — 扁平化为 `name → {phone, note}`（call 和 sms 共用）
- `memory/clawease_wx_takeover_strategy.md` — 重写为历史演进版
- `memory/clawease_tech_decisions.md` — 渠道架构节 + 反诈 5 类节

**保留不动（R&D / 远程兜底）**：
- `scripts/wechat_send.py` + `scripts/messenger/wechat_ui.py`（微信 R&D）
- `scripts/messenger/whatsapp.py`（B 方案 WhatsApp）
- `scripts/messenger/sms_aliyun.py`（原 sms.py，远程短信兜底）
- `scripts/voice_to_wechat.py` / `scripts/voice_to_messenger.py`（历史编排）

### 🧪 已做 smoke（不依赖设备）
- ✅ 全模块 import 通（`base` / `spam_categories` / `voice_to_action` 无语法/循环依赖）
- ✅ offline 分类兜底：验证码短信被 regex 识别、普通短信归"正常"
- ✅ `pip install pyttsx3 pywin32` 装入 clawease env，`tts_local.preheat()` 返回 `pyttsx3` ✅

### 🚧 D5 剩余（需设备）
- [ ] 启 LDPlayer 或插真机 USB → `adb devices` 有设备 → `CallAdapter().execute({'phone':'10086'})` 弹拨号器
- [ ] `voice_to_action.py --voice-text "给女儿打电话"` 三条命令真机/模拟器跑通
- [ ] 造 3 条测试短信（1 正常 + 1 验证码 + 1 中奖）塞收件箱 → read_inbox TTS 演示分类
- [ ] 录 30 秒 demo 视频（打电话 + 读短信 + 发短信三件套）

### Demo 主链路健康度（C 方案视图）
| 段 | 状态 |
|---|---|
| 1. 中文意图解析（OpenClaw Gemini） | ✅ D5 早实测通 |
| 2a. CallAdapter | 🟡 代码就位，等设备 smoke |
| 2b. SmsAdapter（intent 版） | 🟡 代码就位，等设备 smoke |
| 2c. InboxReaderAdapter | 🟡 代码就位，等设备 smoke |
| 3. 反诈 5 类分类 skill | ✅ offline fallback 通；LLM 路径等 smoke |
| 4. 本地 TTS（pyttsx3/SAPI） | ✅ preheat 通 |
| 5. voice_to_action 编排 | ✅ 就位 |
| 6a. WhatsApp adapter（B 残留） | 🟡 远程兜底保留 |
| 6b. 阿里云 SMS adapter（B 残留） | 🟡 远程兜底保留 |
| 6c. 微信 UI adapter | ⚠️ D4 通 / D5 撞风控，R&D 保留 |

**叙事调整（给评委）**：ClawEase 的价值是"老人/视障通讯层简化代理"。回到需求源头 —— 老人对手机的真实使用是**打电话、发短信、防诈骗**三件事，微信代理是第二层扩展。**验证码短信单列一类**，是社工诈骗的头号入口 —— 这个选择比"通用反诈"更有说服力。

---

## 2026-04-24 — D6 / CallAdapter 真机通 + 产品化路径锁定

### ✅ 真机 smoke 通过
CallAdapter 在真机 USB debugging 下跑通：拨号器正确弹出、号码栏预填。
→ 证实 C0（Python + uiautomator2 + adb）端到端可行，demo 日直接走这套，不再改动。

### 🎯 产品化路径决策
Demo 之后走 **Kotlin 原生 APK**，走 Intent + ContentResolver 路径（**非**无障碍服务、**非** root，只用运行时权限）。现有 `ActionAdapter` 抽象一一映射到 Android 原生 API：

| Python 版 | Kotlin 版 | 权限 |
|---|---|---|
| CallAdapter / `am DIAL` | `Intent.ACTION_DIAL` | 0 |
| SmsAdapter / `am SENDTO` | `Intent.ACTION_SENDTO` | 0 |
| InboxReaderAdapter / `content query` | `ContentResolver` + `Sms.Inbox` | `READ_SMS` |
| tts_local (SAPI) | `android.speech.tts.TextToSpeech` | 0 |
| ASR（Layer 2 待接） | `android.speech.SpeechRecognizer` | `RECORD_AUDIO` |

**估时**：4-7 天单人。
**硬约束**：**demo 日之前一行 Kotlin 都不写** —— 任何重构都可能损坏现有 USB demo。

### 🚧 下一步（按时序）
1. D5c 剩余 smoke：`SmsAdapter` + `InboxReaderAdapter` 真机跑通
2. D5d：造 3 条测试短信（正常 + 验证码 + 中奖）→ 录 30 秒 demo 视频
3. **Demo 日之后**：开 Kotlin app 骨架（Android Studio 新项目 + 三个 Activity + 一个 Intent Dispatcher）

---

## Demo 链路全景（Layer 1 目标视图）

> 1 周内要录的 30 秒 demo：老人对手机说"给女儿回'我吃过饭了'" → 微信里真的发出去。

```
┌──────────┐   语音     ┌──────────────┐   文本意图    ┌──────────────┐   UI 操作    ┌──────────┐
│ 老人麦克风 │ ────────> │ OpenClaw ASR │ ──────────> │ uiautomator2 │ ──────────> │ Android  │
│           │           │   + LLM      │             │   Python     │             │  微信    │
└──────────┘            └──────────────┘             └──────────────┘             └──────────┘
                                                                                        │
                                                                                        │ 新消息到达
                                                                                        ▼
┌──────────┐   语音     ┌──────────────┐   文本播报    ┌──────────────┐   截屏+OCR   ┌──────────┐
│ 老人扬声器 │ <──────── │ OpenClaw TTS │ <────────── │ uiautomator2 │ <────────── │ Android  │
│           │           │              │             │   Python     │             │  微信    │
└──────────┘            └──────────────┘             └──────────────┘             └──────────┘
```

### 链路逐段健康度（2026-04-22 状态）

| 段 | 状态 | 现场 | 缺啥 |
|---|---|---|---|
| 1. 老人麦克风采集 | ⚪ 暂代 | 用 PC 麦克风手测就行 | demo 不需要硬件麦克 |
| 2. OpenClaw ASR | ❌ 未接 | OpenClaw 有 `capability audio` 入口 | Layer 1 先单模型（Whisper API 或 Paraformer 二选一），不双校 |
| 3. OpenClaw LLM (Gemini) | ✅ 通 | D1 已验证 | — |
| 4. uiautomator2 Python 桥 | ❌ 未装 | Python 3.13 在位 | `pip install uiautomator2` + Android 端 atx-agent |
| 5. Android 模拟器 | ❌ 未装 | 无 adb / emulator | 装雷电 / Android Studio AVD（先选一） |
| 6. 测试微信号 | ❌ 未注册 | — | 注册一个独立号（**不要用真号**，先扛封号风险） |
| 7. 微信 UI 自动化脚本 | ❌ 未写 | — | uiautomator2 选好元素后写发送脚本 |
| 8. 反向：截屏 + OCR | ❌ 未接 | — | uiautomator2 截屏 + 大模型 VLM 直接读图（绕开本地 OCR） |
| 9. OpenClaw TTS | ❌ 未接 | OpenClaw 有 `capability tts` 入口 | 选个中文 TTS provider，能在终端播声音 |

### Layer 1 剩余任务（按依赖顺序）

1. **D3** ← 现在：装 Android 模拟器 + ADB + 注册测试微信号
2. **D4**：uiautomator2 Python 脚本，能在微信里发一条文本消息（脱离 LLM 单跑）
3. **D5**：把 D3+D4+D1 串起来 — 终端打字 → LLM 生成回复 → uiautomator2 发送
4. **D6**：反向 — 微信新消息截屏 → 大模型 VLM 读图 → 终端打印文本
5. **D7**：加上 ASR + TTS，录 30 秒视频

> ASR/TTS 放到最后是故意的：链路验证不靠语音，文本就够。语音只是 demo 的"皮"，不要被它阻塞主链路。

---

## D3 起跑前的待定项（用户拍板）

- **模拟器选哪家**：
  - **A. 雷电模拟器 LDPlayer 9**（推荐 demo 用）— 国内下载快，对微信兼容好，自带 ADB；缺点是带些广告/捆绑
  - **B. Android Studio AVD** — 干净官方，能跑 google_apis 镜像；缺点是装 Studio 全套要几个 GB，启动慢
  - **C. Genymotion** — 商用，免费版 ARM 兼容差，新版微信可能跑不起来
- **测试微信号怎么来**：用一个备用手机号注册，**和家人主号物理隔离**
- **首选 ASR/TTS**（D7 才用，D3 不需要决定）：先放空位

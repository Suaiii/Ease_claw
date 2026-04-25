# 路演测试短信种子（2026-04-26 live demo）

demo 里"有没有新短信"这一击要让评委看到**三种分类同框**（分类由 `scripts/spam_categories.py` 判定，pill 颜色由 frontend 映射）：
- **验证码**（杀招，"不要告诉任何人"警告前缀）
- **话费订单**（合法业务通知，中性标签；demo 展示"AI 不只识别诈骗，还做生活信息归类"）
- **正常**（家人消息，无前缀）

这三条短信必须在 demo 开始前位于收件箱**最前面**（`read_inbox` 默认按时间倒序取 limit 条，默认 5 条）。

## 三条固定内容（逐字不改）

| 分类 | 发件人（address） | 正文 |
|---|---|---|
| 正常 | `Mom` 或任意真实联系人 | `明天下午 3 点来吃饭，记得带雨伞。` |
| 话费订单 | `10086` | `【中国移动】尊敬的客户，您的4月话费账单已出：本月消费 58.50 元，将于4月25日自动扣款。余额查询请发送 CXYE 到 10086。` |
| 验证码（杀招） | `CMB` 或 `95555` | `【招商银行】您的验证码是 628193，5 分钟内有效，请勿泄露给任何人。` |

> **发送顺序**：正常 → 话费订单 → 验证码。最后发的排在最上面，演示时 inbox card 顺序 = 验证码 → 话费订单 → 正常，第一眼就是"警告前缀 + 业务标签 + 家人留言"的分类对比。

**状态（2026-04-24）**：✅ 正常已塞；⏳ 话费订单待塞；⏳ 验证码待塞。

## 方法 A —— 用第二台手机/SIM 发（推荐，最稳）

最接近真实场景，也绕开 MIUI 对非默认 SMS app 写 content provider 的限制。

1. 从另一部手机给 Xiaomi 13 发上表三条短信，**间隔 5-10 秒**，保证收件箱顺序正确
2. 手机 SMS app 里肉眼确认三条在最顶，且没有别的消息挤进来
3. 若一时没人配合，找店里一个"拍照送话费"扫码、或用 `app.showdoc` 这类在线短信（**⚠️ 不要**用真实银行/运营商发送号，不然触发运营商合规拦截）

## 方法 B —— adb content insert 直写 inbox（MIUI 上大概率失败，仅作兜底）

MIUI / 非 root 环境 `content://sms/inbox` 写权限被屏蔽，但可以试一下：

```powershell
$adb = "E:\aNB\Ease-claw\scripts\adb\platform-tools\adb.exe"

& $adb shell content insert `
  --uri content://sms/inbox `
  --bind address:s:Mom `
  --bind body:s:"明天下午 3 点来吃饭，记得带雨伞。" `
  --bind date:l:$([DateTimeOffset]::Now.ToUnixTimeMilliseconds())

Start-Sleep -Seconds 2

& $adb shell content insert `
  --uri content://sms/inbox `
  --bind address:s:106901234567 `
  --bind body:s:"恭喜您！您已被抽中 iPhone 15 Pro，点击 hxxps://bit.ly/xxx 领取。" `
  --bind date:l:$([DateTimeOffset]::Now.ToUnixTimeMilliseconds())

Start-Sleep -Seconds 2

& $adb shell content insert `
  --uri content://sms/inbox `
  --bind address:s:CMB `
  --bind body:s:"【招商银行】您的验证码是 628193，5 分钟内有效，请勿泄露给任何人。" `
  --bind date:l:$([DateTimeOffset]::Now.ToUnixTimeMilliseconds())
```

如果返回 `java.lang.SecurityException: No permission to access content://sms` → 方法 B 失败，走方法 A。

## 验证（两种方法通用）

1. 手机 SMS app 肉眼检查：三条在最前，顺序 = 验证码 → 中奖 → 正常
2. 跑 demo 服务：
   ```powershell
   & .\start_demo.ps1
   ```
3. Chrome 打开 `http://127.0.0.1:8765`
4. textarea 输入 `有没有新短信`，勾 `limit=5`，取消 `dryRun`，点 Run
5. 期望：**Execution Trace 里 inbox 卡片区渲染 3 条**
   - 第 1 条：黄色 pill（`warn`，验证码）
   - 第 2 条：红色 pill（`bad`，中奖诈骗）
   - 第 3 条：绿色 pill（`ok`，正常）

如果 pill 颜色不对 → 查 `scripts/spam_categories.py` 的 `classify_sms` 是否正确命中；regex 兜底在 OpenClaw 不可用时也应分对类。

## 常见坑

- **收件箱里已有真实短信挤在最顶**：演示前 10 分钟把通知静音，别让验证码 / 外卖推送把我们的三条挤下去
- **中奖短信被运营商反诈拦截**：发件号用普通手机号别用 106 开头。如果还是被拦，演示前手动把"可疑短信"分类的文件夹里那条捞回收件箱
- **MIUI "信息安全" 误判验证码短信**：把 Mi 安全中心的"骚扰拦截"关掉（或只关"验证码"类拦截）
- **date 字段漂移**：方法 B 的 `date:l:xxx` 是毫秒 Unix 时间戳；如果忘了传，inbox 可能把它按 1970 排到最底

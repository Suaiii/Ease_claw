# ClawEase Demo 状态快照（2026-04-25）

更新时间：2026-04-25
环境：`E:\aNB\Ease-claw` + 真机 USB（`adb` 设备在线）

## 1. Demo 资产盘点

- Web 双端页面
  - `demo/index.html`（双栏总览）
  - `demo/elder.html`（老人端）
  - `demo/operator.html`（开发者端）
- Demo 服务端
  - `scripts/demo_server.py`
  - `start_demo.ps1`
  - `start_product.ps1`
  - `stop_product.ps1`
- OpenClaw 云端链路
  - `scripts/start_clawease_cloud.ps1`
  - `scripts/start_openclaw_cloud_relay.ps1`
  - `scripts/openclaw_cloud_intent.mjs`
  - `scripts/stop_clawease_cloud.ps1`
- 主编排入口
  - `scripts/voice_to_action.py`
- 路演与产品说明
  - `notes/demo-script-0426.md`
  - `notes/CURRENT_PRODUCT.md`
  - `notes/ARCHITECTURE.md`
  - `notes/PARSER_AGENT.md`

## 2. 今日实测结果（已跑）

- OpenClaw 云端 helper 可用：
  - `node scripts/openclaw_cloud_intent.mjs "请只回复OK"` 返回 `OK`
- 三条 dry-run 通过（`openclaw_cloud`）：
  - `给10086打电话`：约 3.5s 解析完成
  - `给12306发一条我晚点到`：约 3.8s 解析完成
  - `有没有新短信`：约 3.4s 解析完成
- 三条真机动作链通过（`exit=0`）：
  - `call`：拨号器成功拉起（DIAL）
  - `send_sms`：短信编辑页成功预填（默认不自动发送）
  - `read_inbox`：成功读收件箱并完成分类
- Web Demo 服务在线：
  - `/api/status` 返回 `mode=openclaw_cloud`、`adb.ok=true`
  - `/?view=elder` 与 `/?view=operator` 均返回 200

## 3. 现在最快演示 SOP（2-3 分钟起演）

1. 启动链路（PowerShell）
```powershell
cd E:\aNB\Ease-claw
.\scripts\start_clawease_cloud.ps1
.\start_demo.ps1
```

2. 打开页面（Chrome）
- 双栏总览：`http://127.0.0.1:8765/`
- 老人端：`http://127.0.0.1:8765/?view=elder`
- 开发者端：`http://127.0.0.1:8765/?view=operator`

3. 演示口令（按这个顺序最稳）
- `给10086打电话`
- `给12306发一条我晚点到`
- `有没有新短信`

4. 演示结束
```powershell
.\stop_product.ps1
```

## 4. 现场注意点（避免翻车）

- `voice_to_action.py` 会自动读取 `start.bat` 中的 `HTTP_PROXY/HTTPS_PROXY`，不需要手动再 export。
- `SmsAdapter` 默认 `auto_send=False`，会停在短信编辑页，避免误发。
- 若 `adb` 断开，先看 `adb devices` 是否有 `device`，再重跑。

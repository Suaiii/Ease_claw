# ClawEase — 当前产品面貌

## 一句话

ClawEase 现在是一套面向老人/视障用户的中文语音通讯助手：
用户说一句中文，系统在秒级内理解意图，并完成打电话、发短信、读短信这 3 类高频动作。

## 当前主链

1. 用户输入一句中文命令
2. 云端 OpenClaw 负责意图解析
3. `voice_to_action.py` 把意图路由到本地动作层
4. Python adapter 通过 Android `adb` / `intent` 执行手机操作
5. 收件箱读取结果带反诈分类和本地 TTS 朗读

## 当前已经成立的产品能力

- 中文自然语言意图解析
- 秒级响应的云端 OpenClaw 语义入口
- Android 真机/模拟器拨号
- Android 发短信预填与发送流程
- Android 收件箱读取
- 验证码/诈骗短信分类
- 本地 TTS 朗读短信摘要
- 本地 fallback 兜底，避免模型或网关异常导致整条链失效

## 当前系统分层

### 1. 语义层

- 入口文件: [voice_to_action.py](E:\aNB\Ease-claw\scripts\voice_to_action.py)
- 默认模式: `OPENCLAW_PARSE_MODE=openclaw_cloud`
- 真实语义执行: 云端 OpenClaw

### 2. 动作层

- 拨号: [call.py](E:\aNB\Ease-claw\scripts\messenger\call.py)
- 短信: [sms.py](E:\aNB\Ease-claw\scripts\messenger\sms.py)
- 收件箱: [inbox.py](E:\aNB\Ease-claw\scripts\messenger\inbox.py)

### 3. 安全/稳态层

- 云端网关常驻，本地只做轻量连接
- 设备 token 已落地到项目专用云端 state
- 本地规则 fallback 保底
- relay 固定在本机 loopback，不直接让业务脚本暴露远端公网 ws

## 现在它像什么产品

它已经不是一个“技术演示脚本堆”了，而是一个可工作的语音通讯代理雏形：

- 前台形态: 老人一句话下指令
- 后台形态: OpenClaw 做语义理解，Python 控制手机执行
- 产品定位: “老人/视障用户的一句话通讯助手”

## 还没有完成的部分

### 1. OpenClaw 还不是手机执行层

目前 OpenClaw 负责的是“理解命令”，
真正操作手机的仍然是本地 Python adapter。

所以当前形态是：

- `OpenClaw 驱动的产品链`

不是：

- `OpenClaw 原生工具直接操作手机`

### 2. 标准 OpenClaw CLI 远端操作还未完全收口

业务链已通，但标准 CLI 连接远端网关时仍会触发一条额外的 metadata-change 审批流。

这不影响当前产品主链，但影响“纯 CLI 运维体验”。

### 3. 端到端真机稳定性仍依赖 adb 可用

当手机未连接、adb 失效、ROM selector 变化时，动作层仍需要适配。

## 当前最准确的对外表述

ClawEase 目前已经实现：

- 基于云端 OpenClaw 的中文语义理解
- 基于 Android 原生能力的通讯动作执行
- 面向老人场景的短信反诈分类与朗读

当前版本已经具备 demo 和继续产品化迭代的基础。

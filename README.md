# Grok4Free - Grok Account Auto-Registration Tool

<div align="center">

**基于 Camoufox 反检测浏览器的 Grok/x.ai 账号自动化注册解决方案**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)

</div>

## 📋 项目简介

Grok4Free 是一个完全独立的 Grok 账号自动注册工具，实现了从**创建临时邮箱 → 填写注册表单 → 邮件验证码验证 → Turnstile 人机验证 → OAuth 设备授权 → 提取 refresh_token** 的全流程自动化。

核心特性包括：
- 🔐 **三重邮箱支持**：MoEmail 自动创建 / 微软自有邮箱（Graph API） / 子邮箱模式（防串号设计）
- 🛡️ **反检测机制**：Camoufox 反检测浏览器 + 拟人化鼠标轨迹 + 网络指纹一致性
- 🔄 **智能验证码获取**：自动识别 xAI 验证码格式，支持 Graph/Outlook 双通道轮询
- ⚡ **多进程并发**：1-5 进程并行，错峰启动降低风控风险
- 🎯 **拟人化操作**：随机延迟、坐标抖动、逐字输入模拟真人行为
- 🖥️ **双模运行**：Tkinter 图形界面 + 命令行接口

## 🚀 快速开始

### 1️⃣ 环境准备

```bash
cd /home/danny/projects/Grok4Free

# 安装依赖（会自动下载 GeoIP 数据库，约数百 MB）
pip install -r requirements.txt
```

**系统要求：**
- Python 3.10+
- Linux (推荐) / macOS / Windows
- Firefox 浏览器（由 Camoufox 自动管理）

### 2️⃣ 配置项目

复制配置模板并编辑：

```bash
cp config.example.json config.json
```

**关键配置项说明：**

| 配置项 | 作用 | 必填场景 |
|--------|------|----------|
| `mail_mode` | 邮箱模式选择 | 必须设置 |
| `moemail_api_base` | MoEmail 服务地址 | moemail 模式 |
| `moemail_api_key` | MoEmail API Key | moemail 模式 |
| `proxy` / `proxies` | 代理服务器配置 | 推荐配置 |

#### 三种邮箱模式详解：

**A. MoEmail 模式 (`mail_mode: "moemail"`)**
```json
{
  "mail_mode": "moemail",
  "moemail_api_base": "https://your-moemail-server.com",
  "moemail_api_key": "your-api-key",
  "moemail_domain": "jiayyy.cc.cd",
  "moemail_expiry_ms": 3600000,
  "register_count": 10
}
```
- 自动在 MoEmail 服务上创建临时邮箱
- `register_count` = 要注册的账号数量
- 适合快速批量测试

**B. 微软邮箱模式 (`mail_mode: "msgraph"`)**
```json
{
  "mail_mode": "msgraph",
  "msgraph_accounts": [
    "user1@outlook.com----password123----refresh_token_abc123----client_id_xyz",
    "user2@outlook.com----password456----refresh_token_def456----client_id_xyz"
  ]
}
```
- 使用自备微软邮箱（Outlook/Hotmail）
- 格式：`邮箱----密码----refresh_token----client_id`
- **注册数量 = 邮箱行数**
- 验证码通过 Microsoft Graph API 自动获取
- 适用场景：已有微软账号需要批量注册 Grok

**C. 子邮箱模式 (`mail_mode: "submailbox"`)**
```json
{
  "mail_mode": "submailbox",
  "submailbox_accounts": [
    "sub1@main.com----pass1----rt1----client_id",
    "sub2@main.com----pass2----rt2----client_id"
  ]
}
```
- 微软主邮箱生成的子邮箱
- **特点**：多个子邮箱共用一个收件箱，通过收件人地址过滤防止混淆
- **关键技术**：强制使用 GRAPH scope (`https://graph.microsoft.com/.default`)
- 每个子邮箱需单独配置 token 和 client_id

> 💡 提示：微软邮箱模式的「密码」字段仅为记录用途，实际登录依赖 refresh_token

### 3️⃣ 启动程序

#### 🖱️ 图形界面（推荐新手）

```bash
# 方式 1: 使用启动脚本（自动安装依赖）
./start-gui.sh

# 方式 2: 直接运行
python run.py
```

**GUI 功能：**
- 📧 邮箱模式一键切换（下拉框）
- 📝 实时日志输出与统计面板
- ▶️/⏹️ 开始/停止控制
- ❌ 一键清除保存的邮箱数据

#### 💻 命令行模式

```bash
# MoEmail 批量注册
python run.py register -n 10              # 10 个账号，单进程
python run.py register -n 10 -c 3         # 10 个账号，3 并发

# 微软邮箱模式
python run.py register -m msgraph -c 2    # 读取 config.json 中的 msgraph_accounts

# 子邮箱模式
python run.py register -m submailbox -c 2 # 读取 config.json 中的 submailbox_accounts

# 无头模式（后台运行）
python run.py register -n 5 --headless
```

**参数说明：**
- `-n`, `--register-count`: 注册数量（仅 MoEmail 模式有效）
- `-c`, `--concurrency`: 并发进程数（1-5）
- `-m`, `--mail-mode`: 邮箱模式（moemail/msgraph/submailbox）
- `--headless`: 无头模式（不显示浏览器窗口）

---

## 🎯 核心功能深度解析

### 🔑 OAuth 设备授权流程

注册成功后自动执行 OAuth 2.0 设备授权流：
1. 发现端点（`.well-known/openid-configuration`）
2. 请求 device_code 和用户授权码
3. 等待用户授权（跳转到 `/account` 页面）
4. 轮询获取 `access_token` / `refresh_token` / `id_token`

**安全校验：**
- Endpoint URL 严格验证（必须是 `*.x.ai` 域名的 HTTPS）
- 强制要求响应包含 `refresh_token`
- 网络错误容错（20 次连续重试）

### 📧 智能验证码获取

**MoEmail 通道：**
- 每 3 秒轮询收件箱
- 优先匹配主题格式：`XXX-XXX xAI` 或 `verification code: XXX-XXX`
- 通用匹配：`[A-Z0-9]{3}-[A-Z0-9]{3}` 或 4-8 位数字

**Microsoft Graph 通道：**
- 多租户尝试：transient → consumers → organizations
- 多 Scope 容错：`.default` / `Mail.Read` / `Mail.ReadWrite` / Outlook API
- Graph + Outlook 双渠道互为 fallback

**子邮箱防串号机制：**
```python
def _extract_recipients(message):
    # 提取收件人列表，转小写标准化
    to_emails = [email.lower() for email in to_list]
    return target_address in to_emails
```

### 🤖 拟人化反检测策略

**浏览器指纹：**
- OS: Windows
- Locale: zh-CN  
- Window Size: 1200×800 (worker) / 1400×900 (single)
- User-Agent: 真实 Firefox 特征

**交互模拟：**
- `_human_click()`: 40-110ms 随机延迟
- `human_type()`: 逐字符输入，45-140ms 间隔，6% 概率停顿
- `_human_mouse_move()`: 分段路径 + 随机偏移量

**地理位置一致性：**
- 代理启用 `geoip=True`
- 浏览器地理位置探测与代理出口 IP 匹配

**Turnstile 兜底方案：**
```python
def _human_click_turnstile(page):
    # 1. 等待自动验证（主流情况）
    # 2. iframe 穿透定位 checkbox（src 为空时）
    # 3. 拟人化坐标点击
    # 4. 10 轮重试 × 5s 超时
```

### 🏗️ 多进程架构设计

**调度器（主进程）：**
- 维护 `active_workers < concurrency`
- 代理池轮询分配（确保并发内不重复）
- 单点写入账号结果（避免文件竞争）

**Worker（子进程）：**
- `spawn` 上下文启动（兼容跨平台）
- 每进程独占 Camoufox 实例
- 通过队列回传结果，不直接写文件

**优雅退出：**
- `multiprocessing.Event` 广播取消信号
- 所有步骤前检查 cancel 标志
- 15 秒强制终止超时

---

## 📂 项目结构

```
Grok4Free/
├── run.py                 # CLI/GUI 入口分发器
├── start-gui.sh           # GUI 启动脚本（含依赖自动安装）
├── config.example.json    # 配置模板
├── LICENSE                # Apache2.0 许可证
├── requirements.txt       # Python 依赖
├── src/
│   ├── __init__.py
│   ├── register.py        # 核心注册流程（1281 行）
│   ├── scheduler.py       # 多进程调度器
│   ├── worker.py          # Worker 进程入口
│   ├── config.py          # 配置加载与规范化
│   ├── account_store.py   # 账号持久化（flush+fsync）
│   ├── http_client.py     # curl_cffi HTTP 客户端
│   ├── mail_moemail.py    # MoEmail 临时邮箱服务
│   ├── mail_msgraph.py    # Microsoft Graph/Outlook 取件
│   └── oauth/
│       ├── device.py      # OAuth 2.0 设备授权流
│       ├── proxy_helper.py # 代理解析工具
│       └── __init__.py
└── gui/
    ├── app.py             # Tkinter 图形界面
    ├── styles.py          # 主题样式常量
    └── __init__.py
```

---

## 🔒 安全与隐私

### ✅ 敏感信息保护

本项目严格保护用户隐私，以下文件已被 `.gitignore` 排除：

| 文件类型 | 内容 | 是否公开 |
|---------|------|----------|
| `config.json` | API Key / 代理认证 | ❌ 本地专用 |
| `accounts_*.txt` | 注册成功的账号信息 | ❌ 本地保存 |
| `.camoufox/` | 浏览器缓存数据 | ❌ 本地缓存 |

### ⚠️ 使用前必读

1. **仅限学习研究**：本工具仅供技术学习与安全研究使用
2. **遵守服务条款**：批量注册可能违反目标网站的服务条款
3. **自担风险**：作者不对任何法律后果承担责任
4. **合理使用**：建议单进程低频率操作，避免触发风控

---

## 🐛 常见问题

### Q1: "No such file: camoufox"
**原因：** 未正确安装带 geoip 的版本

```bash
pip uninstall camoufox
pip install "camoufox[geoip]"
```

### Q2: "MoEmail API 调用失败"
**检查清单：**
- `config.json` 中的 `moemail_api_base` 是否有末尾 `/`
- `moemail_api_key` 是否有效且未过期
- 服务器是否可以访问（`ping your-server.com`）

### Q3: "Turnstile 超时"
**解决方案：**
- 更换到稳定性更好的代理节点
- 使用 residential proxy（住宅代理）成功率更高
- 调整 `--headless` 开关（部分情况下隐藏模式更稳定）

### Q4: "微软邮箱取不到验证码"
**诊断步骤：**
1. 检查 `refresh_token` 是否失效（尝试手动刷新）
2. 确认 `client_id` 是否具有 `Mail.Read` 权限
3. 查看日志中的 tenant/scope 尝试记录
4. 子邮箱模式需确认收件人地址过滤逻辑

### Q5: "多并发导致封禁"
**优化建议：**
- 降低并发数至 1
- 延长错峰间隔（修改 scheduler.py 的随机范围）
- 使用不同的代理 IP 分散请求

---

## 📜 开发日志

- **v1.3 (2026-07-28):** 新增子邮箱模式，固定 GRAPH scope + 收件人过滤防串号
- **v1.2 (2026-07-28):** 新增 MS Graph 微软邮箱模式，支持自备邮箱批量注册
- **v1.1 (2026-07-28):** 多进程并发注册 + Turnstile 拟人化点击兜底
- **v1.0 (2026-07-28):** 初始版本，完成从 grok-register 项目独立重构

---

## 🙏 致谢

本项目在研发过程中参考了以下优秀开源项目：

### AaronL725/grok-register
- **地址：** https://github.com/AaronL725/grok-register
- **许可证：** MIT
- **贡献：** OAuth 设备授权流程 (`src/oauth/device.py`)、基础注册逻辑框架

**说明：** Grok4Free 是在原项目基础上进行**完全独立的重构与精简**：
- 移除动态注入等复杂机制，改为显式导入 + 参数传递
- 精简配置项从 60+ 字段降至 10 个核心配置
- 抽离 MS Graph 取件逻辑为新模块 (`src/mail_msgraph.py`)
- 重构 GUI 为 Tkinter 原生实现
- 新增多进程架构、Turnstile 拟人化点击、子邮箱防串号等特性

感谢原作者 AaronL725 的出色工作，为本项目提供了坚实的基础。

---

## 📄 许可证

Apache License 2.0

本项目采用 Apache2.0 许可证开源。使用前请仔细阅读许可证条款：

- ✅ 允许商业使用
- ✅ 允许修改分发
- ✅ 允许私有使用
- ⚠️ 需附带许可证副本
- ⚠️ 需保留版权声明
- ⚠️ 专利授权条款适用

详见 [LICENSE](LICENSE) 文件。

---

<div align="center">

**Made with ❤️ for educational purposes**

*Disclaimer: This tool is provided as-is for learning and research purposes only. The authors are not responsible for any misuse or legal consequences arising from its use.*

</div>

# Grok4Free - Grok 账号自动注册工具

基于 Camoufox 反检测浏览器的 Grok 账号自动注册工具，支持：
- ✅ 三种邮箱模式：MoEmail 临时邮箱 / MS Graph 自备微软邮箱 / 子邮箱（微软主邮箱生成）
- ✅ Turnstile 自动通过（偶发交互式验证支持拟人化点击兜底）
- ✅ OAuth 设备授权自动获取 refresh token
- ✅ 代理支持 + geoip 地理定位
- ✅ 多进程并发注册（1-5 并发，错峰启动）
- 🖥️ GUI + CLI 双模式

## 快速开始

### 1. 安装依赖
```bash
cd /home/danny/projects/Grok4Free
pip install -r requirements.txt
```

### 2. 配置邮箱

复制配置文件并修改：
```bash
cp config.example.json config.json
nano config.json  # 或直接用编辑器打开
```

本工具支持两种邮箱模式，由 `mail_mode` 字段决定：

**模式一：MoEmail（自动创建临时邮箱，`mail_mode: "moemail"`）**
- `moemail_api_base`: MoEmail 服务地址
- `moemail_api_key`: MoEmail API Key
- `moemail_domain`: 收件域名
- 想注册几个就设 `register_count` 为几

**模式二：MS Graph（自备微软邮箱，`mail_mode: "msgraph"`）**
- `msgraph_accounts`: 微软邮箱账号列表，一行一个，格式：
  ```
  邮箱----密码----refresh_token----client_id
  ```
- **有几个邮箱就注册几个**（注册数量 = 邮箱行数）
- 验证码通过 Graph / Outlook API 取件（用 refresh_token + client_id 换 access_token）
- 说明：这里的「密码」是邮箱账号自身密码，仅作记录透传；Grok 会另生成新密码

**模式三：子邮箱（微软主邮箱生成，`mail_mode: "submailbox"`）**
- `submailbox_accounts`: 子邮箱账号列表，一行一个，格式同上：
  ```
  邮箱----密码----令牌----client_id
  ```
- **有几个子邮箱就注册几个**（注册数量 = 行数）
- 子邮箱由微软主邮箱生成，多个子邮箱**共用一个收件系统**、收件地址各不相同；
  因此换 token 固定走 GRAPH（`https://graph.microsoft.com/.default`），
  取件时**按收件人地址过滤**——只提取「收件人 == 该子邮箱地址」的邮件验证码，避免串号
- 出售的子邮箱通常未注册过任何项目，干净可用

### 3. 运行

#### 图形界面模式（推荐）
**双击启动：**
```bash
# Windows: 创建 .lnk 文件指向这个命令
/home/danny/projects/Grok4Free/start-gui.sh

# Linux: 直接执行桌面图标
./Grok4Free.desktop
```

GUI 顶部的「邮箱模式」下拉框可切换 MoEmail / MS Graph / 子邮箱；选择后者两种时会显示对应的多行邮箱输入框。

#### 命令行模式
```bash
# MoEmail 模式：单账号注册
python run.py register -n 1

# MoEmail 模式：批量注册（显示浏览器窗口）
python run.py register -n 5

# 多进程并发注册（-c 指定并发数 1-5，错峰启动）
python run.py register -n 10 -c 3

# MS Graph 模式：读取 config.json 的 msgraph_accounts，数量=邮箱数
python run.py register -m msgraph -c 2

# 子邮箱模式：读取 config.json 的 submailbox_accounts，数量=邮箱数
python run.py register -m submailbox -c 2

# 无头模式（后台运行，不显示浏览器）
python run.py register -n 5 --headless
```

> ⚠️ 推荐 1 并发。多并发注册容易触发风控。

## 功能说明

### GUI 界面
- **邮箱模式下拉框**：切换 MoEmail（自动创建）/ MS Graph（正常微软邮箱）/ 子邮箱
- **MoEmail 配置区 / 微软邮箱 / 子邮箱输入区**：随模式显隐
- **运行日志**：实时显示注册流程日志
- **统计栏**：成功/失败/总数实时统计
- **开始/停止按钮**：控制注册流程

### 输出文件
成功注册的账号保存到项目根目录：
```
accounts_<timestamp>.txt
```
格式：`邮箱----密码----refresh_token`

## 系统要求
- Python 3.10+
- Linux (已验证) / macOS / Windows
- Firefox 浏览器（由 Camoufox 自动管理）

## 注意事项
⚠️ 本工具仅用于学习研究，请勿用于非法用途  
⚠️ MoEmail 有配额限制，请合理使用  
⚠️ 首次运行需要下载 GeoIP 数据库（约几百 MB）

## 故障排查

### 问题 1: "No such file: camoufox"
```bash
# 重新安装带 geoip 的版本
pip uninstall camoufox
pip install "camoufox[geoip]"
```

### 问题 2: "MoEmail API 调用失败"
- 检查 `config.json` 中的 `api_base`、`api_key`、`domain` 是否正确
- 确认 MoEmail 服务可用且账户余额充足

### 问题 3: "Turnstile 超时"
- 尝试切换到有稳定网络环境的代理
- 检查网络连接是否正常

## 开发历史
- v1.0 (2026-07-28): 初始版本，完整实现独立项目重构
- v1.1: 新增多进程并发注册、Turnstile 交互式验证拟人化点击兜底
- v1.2: 新增 MS Graph 微软邮箱取件模式（自备邮箱，数量=邮箱行数）
- v1.3: 新增子邮箱模式（微软主邮箱生成，GRAPH scope + 按收件地址过滤防串号）

## 致谢与来源

本项目基于开源项目 [AaronL725/grok-register](https://github.com/AaronL725/grok-register)（MIT License）发展而来。

在其基础上进行了大量重构与精简：
- 保留 MoEmail 邮箱服务，并抽离 MS Graph 微软邮箱取件（移除其余邮件提供商）
- 去除动态注入等复杂机制，改为显式导入 + 参数传递
- 精简配置项与 GUI
- 新增多进程并发注册、Turnstile 拟人化点击兜底等功能

其中 OAuth 设备授权流程（`src/oauth/device.py`）、MS Graph 取件逻辑（`src/mail_msgraph.py`）
等稳定模块基本沿用/抽离自原项目实现，特此致谢原作者 AaronL725。

## 许可证
MIT License

本项目遵循 MIT 协议，并沿用上游 [grok-register](https://github.com/AaronL725/grok-register) 的 MIT 授权。

---
Made with ❤️ for educational purposes

# Grok4Free - Grok 账号自动注册工具

基于 Camoufox 反检测浏览器的 Grok 账号自动注册工具，支持：
- ✅ MoEmail 临时邮箱自动创建 + 验证码提取
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

### 2. 配置 MoEmail
复制配置文件并修改：
```bash
cp config.example.json config.json
nano config.json  # 或直接用编辑器打开
```

需要填写的字段：
- `moemail_api_base`: MoEmail 服务地址
- `moemail_api_key`: MoEmail API Key
- `moemail_domain`: 收件域名

### 3. 运行

#### 图形界面模式（推荐）
**双击启动：**
```bash
# Windows: 创建 .lnk 文件指向这个命令
/home/danny/projects/Grok4Free/start-gui.sh

# Linux: 直接执行桌面图标
./Grok4Free.desktop
```

#### 命令行模式
```bash
# 单账号注册
python run.py register -n 1

# 批量注册（显示浏览器窗口）
python run.py register -n 5

# 多进程并发注册（-c 指定并发数 1-5，错峰启动）
python run.py register -n 10 -c 3

# 无头模式（后台运行，不显示浏览器）
python run.py register -n 5 --headless
```

> ⚠️ 推荐 1 并发。多并发注册容易触发风控。

## 功能说明

### GUI 界面
- **MoEmail 配置区**：实时编辑保存配置
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

## 致谢与来源

本项目基于开源项目 [AaronL725/grok-register](https://github.com/AaronL725/grok-register)（MIT License）发展而来。

在其基础上进行了大量重构与精简：
- 仅保留 MoEmail 邮箱服务，移除其余邮件提供商
- 去除动态注入等复杂机制，改为显式导入 + 参数传递
- 精简配置项（60+ → 6）与 GUI（1300+ 行 → 360 行）
- 新增多进程并发注册、Turnstile 拟人化点击兜底等功能

其中 OAuth 设备授权流程（`src/oauth/device.py`）等稳定模块基本沿用原项目实现，
特此致谢原作者 AaronL725。

## 许可证
MIT License

本项目遵循 MIT 协议，并沿用上游 [grok-register](https://github.com/AaronL725/grok-register) 的 MIT 授权。

---
Made with ❤️ for educational purposes

# Grok4Free - 快速部署指南

## 🚀 一键启动（推荐）

### Linux / macOS

```bash
chmod +x start-gui.sh
./start-gui.sh
```

### Windows

双击 `start-gui.bat` 或右键 → "以管理员身份运行"

---

## 📋 脚本功能

两个启动脚本自动完成以下操作：

1. ✅ **检查 Python 版本**（要求 3.10+）
2. ✅ **创建虚拟环境**（`.venv/`）
3. ✅ **自动安装依赖**（camoufox[geoip] + curl_cffi）
4. ✅ **检测配置文件**（自动生成 config.json）
5. ✅ **启动 GUI 界面**

---

## ⚙️ 首次运行流程

```bash
# 1. 执行启动脚本
./start-gui.sh  # Linux
start-gui.bat   # Windows

# 2. 会自动生成 config.json
# 3. 编辑配置文件
nano config.json  # Linux
notepad config.json  # Windows

# 4. 再次运行脚本即可启动
```

---

## 🔧 手动部署（进阶）

如果自动脚本不工作，可以手动部署：

### 1. 创建虚拟环境
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux
.venv\Scripts\activate     # Windows
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 准备配置
```bash
cp config.example.json config.json
# 编辑 config.json
```

### 4. 启动程序
```bash
python run.py
```

---

## 💡 常见问题

**Q: 脚本没有执行权限？**  
A: `chmod +x start-gui.sh`

**Q: Python 版本太低？**  
A: 需要 Python 3.10+，请升级系统 Python

**Q: GeoIP 数据库下载慢？**  
A: camoufox 首次运行会下载约数百 MB，请确保网络稳定

**Q: 双击 BAT 文件没反应？**  
A: 右键 → "以管理员身份运行"，或检查 Windows Defender 是否拦截

---

## 🐛 故障排除

### Linux 报错 "No module named camoufox"
```bash
source .venv/bin/activate
pip install --upgrade "camoufox[geoip]"
```

### Windows 报错 "'python' is not recognized"
- 确保安装了 Python 3.10+
- 勾选 "Add Python to PATH"
- 重启命令行

### 虚拟环境激活失败
```bash
rm -rf .venv
./start-gui.sh  # 重新创建
```

---

## 📦 完整版部署清单

| 组件 | 用途 | 状态 |
|------|------|------|
| `start-gui.sh` / `.bat` | 一键启动脚本 | ✅ |
| `.venv/` | Python 虚拟环境 | ✅ 自动生成 |
| `requirements.txt` | Python 依赖列表 | ✅ |
| `config.example.json` | 配置模板 | ✅ |
| `config.json` | 实际配置（需手动填写） | ⚠️ 首次生成 |
| `src/` | 核心代码 | ✅ |
| `gui/` | 图形界面 | ✅ |

---

<div align="center">

**Made with ❤️ for educational purposes**

</div>

#!/bin/bash
# Grok4Free - Linux 启动脚本
# 版本：v0.1.0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Grok4Free v0.1.0 - Linux 启动器"
echo "=========================================="
echo ""

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：未找到 Python3，请先安装："
    echo "   Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "   CentOS/RHEL:   sudo yum install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "✓ Python 版本：$PYTHON_VERSION"

# 检查 Python 版本 >= 3.10
VERSION_OK=false
if [[ $(echo $PYTHON_VERSION | cut -d. -f1) -gt 3 ]] || [[ $(echo $PYTHON_VERSION | cut -d. -f1) -eq 3 && $(echo $PYTHON_VERSION | cut -d. -f2) -ge 10 ]]; then
    VERSION_OK=true
fi
if [ "$VERSION_OK" = false ]; then
    echo "❌ 错误：需要 Python 3.10+，当前版本：$PYTHON_VERSION"
    exit 1
fi

# 检查或安装虚拟环境
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "🔧 正在创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 检查并安装依赖
echo ""
echo "📦 检查依赖..."
if ! python -c "import camoufox" 2>/dev/null; then
    echo "⚠️  检测到 camoufox 未安装，开始安装..."
    pip install -q "camoufox[geoip]"
    echo "✓ camoufox 安装完成"
fi

if ! python -c "import curl_cffi" 2>/dev/null; then
    echo "⚠️  检测到 curl_cffi 未安装，开始安装..."
    pip install -q curl_cffi
    echo "✓ curl_cffi 安装完成"
fi

# 检查 config.json
if [ ! -f "config.json" ]; then
    echo ""
    echo "⚙️  配置文件不存在，从模板创建..."
    cp config.example.json config.json
    echo "✅ 已创建 config.json，请编辑后再运行："
    echo "   nano config.json"
    echo ""
    deactivate
    exit 0
fi

echo ""
echo "=========================================="
echo "✅ 环境准备完成，启动 GUI..."
echo "=========================================="
echo ""

# 启动 GUI
python run.py

# 退出时保持窗口（可选）
# read -p "按回车键退出..."

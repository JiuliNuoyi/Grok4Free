#!/bin/bash
# Grok4Free GUI 启动脚本（优化版）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "=========================================="
echo "🚀 Grok4Free GUI 启动中..."
echo "=========================================="

# 优先使用项目的 .venv
if [ -f ".venv/bin/python" ]; then
    VENV_PYTHON=".venv/bin/python"
    echo "✅ 使用项目虚拟环境 Python"
elif command -v python3 &> /dev/null; then
    VENV_PYTHON="python3"
    echo "⚠️ 使用系统 Python3"
else
    echo "❌ 未找到 Python，请先安装: sudo apt install python3 python3-tk"
    exit 1
fi

# 检查依赖（含 geoip extra）
if ! $VENV_PYTHON -c "import camoufox, geoip2" 2>/dev/null; then
    echo "[!] 检测到依赖未安装（或缺少 geoip）..."
    $VENV_PYTHON -m pip install --break-system-packages -q "camoufox[geoip]" curl_cffi 2>/dev/null || \
    $VENV_PYTHON -m pip install -q "camoufox[geoip]" curl_cffi
    echo "✅ 依赖已安装"
fi

# 检查 config.json
if [ ! -f "config.json" ]; then
    echo "⚠️  config.json 不存在，将使用默认配置"
    cp config.example.json config.json 2>/dev/null || true
fi

echo ""
echo "📝 GUI 准备就绪！"
echo ""

# 启动 GUI
exec $VENV_PYTHON run.py gui

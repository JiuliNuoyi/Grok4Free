@echo off
chcp 65001 >nul
rem Grok4Free - Windows 启动脚本
rem 版本：v0.1.0

title Grok4Free v0.1.0

echo ==========================================
echo Grok4Free v0.1.0 - Windows Launcher
echo ==========================================
echo.

cd /d "%~dp0"

rem 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误：未找到 Python，请先安装 Python 3.10+
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PY_VERSION=%%i
echo ✓ Python 版本：%PY_VERSION%

rem 检查虚拟环境
if not exist ".venv" (
    echo.
    echo 🔧 正在创建虚拟环境...
    python -m venv .venv
)

rem 激活虚拟环境
call .venv\Scripts\activate.bat

rem 检查并安装依赖
echo.
echo 📦 检查依赖...
python -c "import camoufox" 2>nul
if %errorlevel% neq 0 (
    echo ⚠️  检测到 camoufox 未安装，开始安装...
    pip install --quiet "camoufox[geoip]"
    echo ✓ camoufox 安装完成
)

python -c "import curl_cffi" 2>nul
if %errorlevel% neq 0 (
    echo ⚠️  检测到 curl_cffi 未安装，开始安装...
    pip install --quiet curl_cffi
    echo ✓ curl_cffi 安装完成
)

rem 检查 config.json
if not exist "config.json" (
    echo.
    echo ⚙️  配置文件不存在，从模板创建...
    copy /y config.example.json config.json
    echo ✅ 已创建 config.json，请编辑后再运行：
    echo    Notepad config.json
    echo.
    deactivate
    pause
    exit /b 0
)

echo.
echo ==========================================
echo ✅ 环境准备完成，启动 GUI...
echo ==========================================
echo.

run.py

deactivate
pause

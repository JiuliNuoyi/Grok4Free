#!/usr/bin/env python3
"""全面验证测试脚本。

检查所有模块、配置、依赖是否正常。
"""

import sys
import os
import json

sys.path.insert(0, "/home/danny/projects/Grok4Free")

def print_header(title):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def test_syntax():
    """语法检查"""
    print_header("1. 语法检查")
    
    files = [
        "src/config.py",
        "src/http_client.py", 
        "src/account_store.py",
        "src/mail_moemail.py",
        "src/register.py",
        "src/oauth/device.py",
        "src/oauth/proxy_helper.py",
        "gui/app.py",
        "run.py",
    ]
    
    all_pass = True
    for f in files:
        try:
            with open(f) as file:
                compile(file.read(), f, 'exec')
            print(f"✅ {f}")
        except Exception as e:
            print(f"❌ {f}: {e}")
            all_pass = False
    
    return all_pass

def test_imports():
    """导入测试"""
    print_header("2. 模块导入测试")
    
    modules = [
        ("src.config", "加载配置"),
        ("src.http_client", "HTTP 客户端"),
        ("src.account_store", "账号存储"),
        ("src.mail_moemail", "MoEmail 邮箱"),
        ("src.oauth.device", "OAuth 设备授权"),
        ("src.oauth.proxy_helper", "代理解析"),
        ("src.register", "主注册流程"),
        ("gui.app", "GUI 界面"),
    ]
    
    all_pass = True
    for module_name, desc in modules:
        try:
            __import__(module_name)
            print(f"✅ {desc} ({module_name})")
        except Exception as e:
            print(f"❌ {desc}: {e}")
            all_pass = False
    
    return all_pass

def test_config():
    """配置检查"""
    print_header("3. 配置文件检查")
    
    config_path = "/home/danny/projects/Grok4Free/config.json"
    
    if not os.path.exists(config_path):
        print("⚠️  config.json 不存在（需要手动创建）")
        
        # 读取示例文件
        example_path = "/home/danny/projects/Grok4Free/config.example.json"
        if os.path.exists(example_path):
            with open(example_path) as f:
                print("\n📋 config.example.json 内容:")
                print(f.read())
        
        return False
    
    try:
        with open(config_path) as f:
            cfg = json.load(f)
        
        required_keys = ["moemail_api_base", "moemail_api_key", "moemail_domain"]
        
        print("✅ config.json 存在且格式正确")
        print("\n当前配置:")
        for key in required_keys:
            value = cfg.get(key, "(未设置)")
            if key == "moemail_api_key":
                value = value[:10] + "..." if len(value) > 10 else value
            print(f"  - {key}: {value}")
        
        if all(cfg.get(k) for k in required_keys):
            print("\n✅ 必要配置齐全，可以运行！")
            return True
        else:
            missing = [k for k in required_keys if not cfg.get(k)]
            print(f"\n⚠️  缺少以下配置：{', '.join(missing)}")
            print("请在 GUI 中配置或编辑 config.json")
            return False
            
    except Exception as e:
        print(f"❌ 读取 config.json 失败：{e}")
        return False

def test_dependencies():
    """依赖包检查"""
    print_header("4. 依赖包检查")
    
    packages = [
        ("camoufox", "反检测浏览器"),
        ("curl_cffi", "HTTP 客户端"),
        ("geoip2", "GeoIP 地理定位 (camoufox[geoip])"),
    ]
    
    all_pass = True
    for pkg_name, desc in packages:
        try:
            __import__(pkg_name)
            print(f"✅ {desc} ({pkg_name})")
        except ImportError as e:
            print(f"❌ {desc}: {e}")
            all_pass = False
    
    return all_pass

def test_functions():
    """功能函数测试"""
    print_header("5. 功能函数可用性测试")
    
    tests = [
        ("from src import config", "config.cfg"),
        ("from src.mail_moemail import generate_username", "username()"),
        ("from src.oauth.device import CLIENT_ID", "oauth.CLIENT_ID"),
    ]
    
    all_pass = True
    for code, name in tests:
        try:
            exec(code)
            print(f"✅ {name} OK")
        except Exception as e:
            print(f"❌ {name}: {e}")
            all_pass = False
    
    return all_pass

def main():
    print("\n" + "🔍 Grok4Free 项目验证".center(60))
    
    results = {
        "语法检查": test_syntax(),
        "模块导入": test_imports(),
        "配置文件": test_config(),
        "依赖包": test_dependencies(),
        "功能函数": test_functions(),
    }
    
    # 总结
    print_header("6. 验证总结")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
    
    print(f"\n总计：{passed}/{total} 项通过")
    
    if passed == total:
        print("\n🎉 全部验证通过！项目已就绪，可以开始使用啦！")
        print("\n🚀 启动方式:")
        print("  - GUI: ./start-gui.sh 或 点击桌面图标 'Grok4Free'")
        print("  - CLI: python run.py register [-n N]")
        return 0
    else:
        print("\n⚠️  仍有问题需要解决，请根据上面的错误信息修复")
        return 1

if __name__ == "__main__":
    sys.exit(main())

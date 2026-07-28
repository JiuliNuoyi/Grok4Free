"""配置加载：读取/保存 config.json。

替代原项目臃肿的 app_config.py（60+ 字段 + 动态注入），
只保留 MoEmail + 代理 + 注册数量共 6 个字段。
"""

import json
import os

# 配置文件默认路径（项目根目录）
CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config.json",
)

DEFAULT_CONFIG = {
    "moemail_api_base": "",
    "moemail_api_key": "",
    "moemail_domain": "",
    "moemail_expiry_ms": 3600000,
    "proxy": "",
    "register_count": 1,
}


def load_config(path=None):
    """加载配置，缺失字段用默认值补齐。文件不存在时返回默认配置。"""
    path = path or CONFIG_FILE
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                for key in DEFAULT_CONFIG:
                    if key in data:
                        config[key] = data[key]
        except Exception as exc:
            print(f"[!] 读取配置失败，使用默认值: {exc}")
    return config


def save_config(config, path=None):
    """保存配置到 config.json（只写已知字段）。"""
    path = path or CONFIG_FILE
    data = {key: config.get(key, DEFAULT_CONFIG[key]) for key in DEFAULT_CONFIG}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=4)
    return path


# ---- 便捷读取器（规范化处理，替代原项目的 get_moemail_* 系列） ----

def get_moemail_api_base(config):
    return str(config.get("moemail_api_base", "") or "").strip().rstrip("/")


def get_moemail_api_key(config):
    return str(config.get("moemail_api_key", "") or "").strip()


def get_moemail_domain(config):
    return str(config.get("moemail_domain", "") or "").strip().lstrip("@")


def get_moemail_expiry_ms(config):
    try:
        return int(config.get("moemail_expiry_ms", 3600000) or 0)
    except (TypeError, ValueError):
        return 3600000


def get_proxy(config):
    return str(config.get("proxy", "") or "").strip()


def get_register_count(config):
    try:
        return max(int(config.get("register_count", 1) or 1), 1)
    except (TypeError, ValueError):
        return 1

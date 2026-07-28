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
    "proxies": [],
    "register_count": 1,
    "concurrency": 1,
    "mail_mode": "moemail",       # "moemail" / "msgraph"（正常微软邮箱）/ "submailbox"（子邮箱）
    "msgraph_accounts": [],       # 微软邮箱账号列表，每项为 "邮箱----密码----refresh_token----client_id"
    "submailbox_accounts": [],    # 子邮箱账号列表，格式同上（收件系统共享，按收件地址过滤）
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


def get_proxies(config):
    """返回代理列表（去重、去空）。

    优先读多行的 'proxies' 字段（列表或换行分隔字符串）；
    若为空则回退到单个 'proxy' 字段。返回 list[str]，可能为空。
    """
    raw = config.get("proxies", None)
    items = []
    if isinstance(raw, list):
        items = [str(x).strip() for x in raw]
    elif isinstance(raw, str):
        items = [ln.strip() for ln in raw.replace("\r", "\n").split("\n")]
    # 回退到单个 proxy
    if not any(items):
        single = get_proxy(config)
        if single:
            items = [single]
    # 去空、去重（保持顺序）
    seen = set()
    result = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            result.append(it)
    return result


def get_register_count(config):
    try:
        return max(int(config.get("register_count", 1) or 1), 1)
    except (TypeError, ValueError):
        return 1


def get_concurrency(config):
    try:
        return max(1, min(int(config.get("concurrency", 1) or 1), 5))
    except (TypeError, ValueError):
        return 1


def get_mail_mode(config):
    """返回邮箱模式：'moemail' / 'msgraph' / 'submailbox'（默认 moemail）。"""
    mode = str(config.get("mail_mode", "moemail") or "moemail").strip().lower()
    if mode in ("msgraph", "submailbox"):
        return mode
    return "moemail"


def _clean_lines(raw):
    """把 list 或换行字符串清洗成去空去重列表（保持顺序）。"""
    items = []
    if isinstance(raw, list):
        items = [str(x).strip() for x in raw]
    elif isinstance(raw, str):
        items = [ln.strip() for ln in raw.replace("\r", "\n").split("\n")]
    seen = set()
    result = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            result.append(it)
    return result


def get_msgraph_accounts(config):
    """返回正常微软邮箱账号原始行列表（去空、去重、保持顺序）。

    支持 list 或换行分隔字符串。每项形如
    '邮箱----密码----refresh_token----client_id'（此函数不解析字段，只做清洗）。
    """
    return _clean_lines(config.get("msgraph_accounts", None))


def get_submailbox_accounts(config):
    """返回子邮箱账号原始行列表（去空、去重、保持顺序），格式同 msgraph。"""
    return _clean_lines(config.get("submailbox_accounts", None))

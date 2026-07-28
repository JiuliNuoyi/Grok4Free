"""代理辅助：解析代理配置。

从原项目 cpa_xai/proxyutil.py 精简而来。原文件含一整套本地 TCP 代理桥
（给 DrissionPage/Chromium 的认证代理用），但 Camoufox 走 Playwright 原生 proxy，
不需要代理桥。这里只保留 device.py 依赖的 resolve_proxy 及其运行时代理支持。
"""

import os
import threading

_tls = threading.local()


def set_runtime_proxy(proxy):
    """设置当前线程的运行时代理（可选，供 OAuth 请求临时覆盖）。"""
    value = str(proxy or "").strip()
    _tls.proxy = value or None


def get_runtime_proxy():
    """读取当前线程的运行时代理。"""
    return getattr(_tls, "proxy", None)


def resolve_proxy(explicit=None):
    """按优先级解析代理：显式参数 > 运行时代理 > 环境变量。返回字符串（无则空串）。"""
    for candidate in (
        str(explicit or "").strip(),
        str(get_runtime_proxy() or "").strip(),
        str(os.environ.get("https_proxy") or "").strip(),
        str(os.environ.get("HTTPS_PROXY") or "").strip(),
        str(os.environ.get("http_proxy") or "").strip(),
        str(os.environ.get("HTTP_PROXY") or "").strip(),
    ):
        if candidate:
            return candidate
    return ""

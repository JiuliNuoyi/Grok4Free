"""HTTP 客户端：基于 curl_cffi 的 http_get / http_post，支持代理。

替代原项目 browser_runtime.py 的 HTTP 部分。去掉了 stealth/DrissionPage/
代理桥/proxy_strict 回退等复杂逻辑，改为显式传入 proxy（不再依赖全局状态）。
"""

from curl_cffi import requests

DEFAULT_TIMEOUT = 20


def _proxies(proxy):
    """把代理字符串转成 curl_cffi 的 proxies 字典；无代理返回 None。"""
    raw = str(proxy or "").strip()
    if not raw:
        return None
    return {"http": raw, "https": raw}


def http_get(url, proxy=None, **kwargs):
    """发起 GET 请求。proxy 为代理字符串（可空）。其余参数透传给 curl_cffi。"""
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    proxies = _proxies(proxy)
    if proxies is not None:
        kwargs.setdefault("proxies", proxies)
    return requests.get(url, **kwargs)


def http_post(url, proxy=None, **kwargs):
    """发起 POST 请求。proxy 为代理字符串（可空）。其余参数透传给 curl_cffi。"""
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    proxies = _proxies(proxy)
    if proxies is not None:
        kwargs.setdefault("proxies", proxies)
    return requests.post(url, **kwargs)

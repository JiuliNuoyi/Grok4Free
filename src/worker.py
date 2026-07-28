"""多进程注册 worker。

每个 worker 在独立进程中运行，启动自己的 Camoufox 浏览器，完成一次注册 + OAuth
授权 + token 获取，然后把结果通过队列回传给主进程。

设计要点：
- 子进程入口必须是干净的模块级函数（Linux fork 时不能携带 Tkinter/GUI 对象）。
- 日志：子进程内所有 print 通过 _QueueLogRedirect 重定向到 log_queue，主进程消费。
- 停止：主进程 set() 一个 multiprocessing.Event，子进程的 cancel_callback 检查它。
- 账号保存：子进程不写文件，把账号信息放进 result_queue，由主进程单点写入。
- 日志行会自动加上 [#worker_id] 前缀，便于在混合日志中区分来源。
"""

import sys
import os
import time
import random
import contextlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _QueueLogRedirect:
    """把 print 输出按行转发到 multiprocessing 队列，并加进程编号前缀。"""

    def __init__(self, worker_id, log_queue, original=None):
        self._wid = worker_id
        self._queue = log_queue
        self._original = original
        self._buffer = ""

    def write(self, text):
        if self._original:
            try:
                self._original.write(text)
            except Exception:
                pass
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                try:
                    self._queue.put(("log", self._wid, f"[#{self._wid}] {line}"))
                except Exception:
                    pass

    def flush(self):
        if self._original:
            try:
                self._original.flush()
            except Exception:
                pass


def _make_cancel_callback(stop_event):
    """把 multiprocessing.Event 包装成 register 需要的 cancel_callback。"""
    def _cancel():
        try:
            return stop_event.is_set()
        except Exception:
            return False
    return _cancel


def run_worker(worker_id, config_dict, log_queue, result_queue, stop_event,
               headless=False):
    """单个注册任务的子进程入口。

    Args:
        worker_id:    进程编号（用于日志前缀）
        config_dict:  配置字典（保留参数，主进程已把配置写入共享 config.json）
        log_queue:    日志队列，(kind, worker_id, payload)
        result_queue: 结果队列，(kind, worker_id, payload)
        stop_event:   停止信号
        headless:     是否无头
    """
    # 所有 worker 共用同一份 config.json（相同 moemail + 相同代理），
    # 注册过程中配置只读，无写竞争。主进程在启动 worker 前已保存好配置。

    redirect = _QueueLogRedirect(worker_id, log_queue, sys.__stdout__)

    result = {"ok": False, "error": "未知错误"}
    try:
        with contextlib.redirect_stdout(redirect), contextlib.redirect_stderr(redirect):
            # 延迟导入，确保 stdout 已重定向且在子进程上下文中
            from src.register import (
                get_proxy_config, run_live, CancelledError, build_profile,
            )
            from camoufox.sync_api import Camoufox

            cancel_cb = _make_cancel_callback(stop_event)

            if cancel_cb():
                result = {"ok": False, "error": "启动前已停止", "cancelled": True}
                result_queue.put(("result", worker_id, result))
                return

            pw_proxy, raw_proxy = get_proxy_config()
            if pw_proxy:
                print(f"[*] 使用代理：{pw_proxy['server']}"
                      + ("（含账号密码认证）" if pw_proxy.get("username") else ""), flush=True)
            else:
                print("[*] 未配置代理，浏览器将直连", flush=True)

            state = {"pos": None}
            camoufox_kwargs = dict(
                headless=headless,
                humanize=True,
                os="windows",
                locale="zh-CN",
                firefox_user_prefs={
                    "intl.accept_languages": "zh-CN,zh,en-US,en",
                    "intl.locale.requested": "zh-CN",
                },
                window=[1200, 800],
            )
            if pw_proxy:
                camoufox_kwargs["proxy"] = pw_proxy
                camoufox_kwargs["geoip"] = True

            try:
                with Camoufox(**camoufox_kwargs) as browser:
                    print("✅ Camoufox 启动成功！", flush=True)
                    page = browser.new_page()
                    # 多进程模式：不在子进程写文件，账号回传主进程统一保存
                    result = run_live(
                        page, state, proxy=raw_proxy,
                        cancel_callback=cancel_cb, save_to_file=False,
                    )
            except CancelledError:
                print("\n[!] 已停止当前注册（浏览器已关闭）", flush=True)
                result = {"ok": False, "error": "用户停止", "cancelled": True}
            except Exception as e:
                if "cancelled" in str(e).lower() or "取消" in str(e):
                    print("\n[!] 已停止当前注册（浏览器已关闭）", flush=True)
                    result = {"ok": False, "error": "用户停止", "cancelled": True}
                else:
                    print(f"❌ 运行失败：{e}", flush=True)
                    import traceback
                    traceback.print_exc()
                    result = {"ok": False, "error": str(e)}
    except Exception as e:
        result = {"ok": False, "error": f"worker 异常：{e}"}

    try:
        result_queue.put(("result", worker_id, result))
    except Exception:
        pass

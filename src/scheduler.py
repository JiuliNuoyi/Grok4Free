"""多进程注册调度器。

负责在主进程侧管理 worker 进程池：
- 维持最多 `concurrency` 个 worker 同时运行（完成一个补一个）。
- 错峰启动：每个 worker 之间随机间隔若干秒，降低风控。
- 汇总日志与结果队列，通过回调转发给 GUI。
- 一键停止：设置 stop_event 通知所有 worker，超时后强杀。
- 账号单点写入：结果里带账号信息的，由本调度器统一写入文件。

调度器运行在主进程的一个后台线程里（不是进程），只做管理和 I/O 转发，
真正的浏览器工作全在子进程。
"""

import os
import time
import random
import multiprocessing as mp

from .worker import run_worker
from .account_store import append_account


class RegistrationScheduler:
    """管理多进程注册任务的调度器。"""

    def __init__(self, config_dict, total, concurrency, headless=False,
                 log_callback=None, result_callback=None,
                 stagger_min=2.0, stagger_max=5.0):
        """
        Args:
            config_dict:     配置字典
            total:           要注册的账号总数
            concurrency:     最大并发进程数（1-5）
            headless:        是否无头
            log_callback:    log_callback(worker_id, line) 转发日志到 GUI
            result_callback: result_callback(worker_id, result) 每个任务完成时回调
            stagger_min/max: 错峰启动的随机间隔范围（秒）
        """
        self.config_dict = config_dict
        self.total = max(int(total), 1)
        self.concurrency = max(1, min(int(concurrency), 5))
        self.headless = headless
        self.log_callback = log_callback
        self.result_callback = result_callback
        self.stagger_min = stagger_min
        self.stagger_max = stagger_max

        self._ctx = mp.get_context("spawn")  # spawn：跨平台一致，避免 fork 带进 GUI 对象
        self.log_queue = self._ctx.Queue()
        self.result_queue = self._ctx.Queue()
        self.stop_event = self._ctx.Event()

        self.success_count = 0
        self.fail_count = 0
        self._out_file = None

    def _log(self, worker_id, line):
        if self.log_callback:
            try:
                self.log_callback(worker_id, line)
            except Exception:
                pass

    def _get_out_file(self):
        if self._out_file is None:
            ts = time.strftime("%Y%m%d")
            self._out_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                f"accounts_{ts}.txt",
            )
        return self._out_file

    def _save_account(self, result):
        """主进程单点写入账号，避免多进程文件竞争。"""
        try:
            email = result.get("email")
            password = result.get("password")
            rt = result.get("rt")
            if email and password and rt:
                path = self._get_out_file()
                append_account(path, email, password, rt)
                self._log(0, f"[主进程] 💾 账号已保存：{email}----{password}----{rt[:20]}...")
        except Exception as e:
            self._log(0, f"[主进程] ⚠️ 保存账号失败：{e}")

    def request_stop(self):
        """请求停止：通知所有 worker。"""
        try:
            self.stop_event.set()
        except Exception:
            pass

    def _drain_logs(self):
        """把日志队列里现有的内容全部转发出去。"""
        while True:
            try:
                kind, wid, payload = self.log_queue.get_nowait()
            except Exception:
                break
            if kind == "log":
                self._log(wid, payload)

    def run(self):
        """主调度循环（阻塞，应在后台线程中调用）。

        Returns:
            (success_count, fail_count, total_done)
        """
        next_id = 1               # 下一个要分配的任务编号
        launched = 0              # 已启动的任务数
        done = 0                  # 已完成的任务数
        active = {}               # worker_id -> Process

        self._log(0, f"[主进程] 🚀 开始批量注册：总数 {self.total}，并发 {self.concurrency}")

        while done < self.total:
            # 若已请求停止，跳出启动循环
            if self.stop_event.is_set():
                self._log(0, "[主进程] 🛑 收到停止请求，停止派发新任务")
                break

            # 维持活跃进程数 <= 并发上限，且还有未派发的任务
            while (len(active) < self.concurrency and launched < self.total
                   and not self.stop_event.is_set()):
                wid = next_id
                next_id += 1
                launched += 1
                p = self._ctx.Process(
                    target=run_worker,
                    args=(wid, self.config_dict, self.log_queue,
                          self.result_queue, self.stop_event, self.headless),
                    daemon=True,
                )
                p.start()
                active[wid] = p
                self._log(0, f"[主进程] ▶️ 启动任务 #{wid}（活跃 {len(active)}/{self.concurrency}）")

                # 错峰：启动下一个前随机等待（仍要转发日志）
                if len(active) < self.concurrency and launched < self.total:
                    delay = random.uniform(self.stagger_min, self.stagger_max)
                    stop_at = time.time() + delay
                    while time.time() < stop_at:
                        self._drain_logs()
                        self._collect_results(active, on_done=lambda: None)
                        if self.stop_event.is_set():
                            break
                        time.sleep(0.2)

            # 转发日志 + 收集已完成的结果
            self._drain_logs()
            done = self._collect_results(active, base_done=done)

            # 若停止了且所有活跃进程都结束了，退出
            if self.stop_event.is_set() and not active:
                break

            time.sleep(0.2)

        # 停止收尾：等待/强杀剩余进程
        if self.stop_event.is_set():
            self._log(0, "[主进程] ⏳ 等待进程响应停止…")
            deadline = time.time() + 15
            while active and time.time() < deadline:
                self._drain_logs()
                done = self._collect_results(active, base_done=done)
                time.sleep(0.3)
            # 强杀仍存活的
            for wid, p in list(active.items()):
                if p.is_alive():
                    self._log(0, f"[主进程] 🔪 强制终止任务 #{wid}")
                    try:
                        p.terminate()
                    except Exception:
                        pass
                active.pop(wid, None)

        # 最终把残余日志/结果清空
        self._drain_logs()
        self._collect_results(active, base_done=done, final=True)

        total_done = self.success_count + self.fail_count
        self._log(0, f"[主进程] ✅ 批量注册结束：成功 {self.success_count} | "
                     f"失败 {self.fail_count} | 完成 {total_done}")
        return self.success_count, self.fail_count, total_done

    def _collect_results(self, active, base_done=0, on_done=None, final=False):
        """收集结果队列，更新计数并清理已结束进程。返回累计完成数。"""
        done = base_done
        while True:
            try:
                kind, wid, result = self.result_queue.get_nowait()
            except Exception:
                break
            if kind != "result":
                continue

            cancelled = result.get("cancelled")
            if result.get("ok"):
                self.success_count += 1
                self._save_account(result)
            elif not cancelled:
                self.fail_count += 1

            done += 1
            if self.result_callback:
                try:
                    self.result_callback(wid, result)
                except Exception:
                    pass

            # 清理该进程
            p = active.pop(wid, None)
            if p is not None:
                try:
                    p.join(timeout=1)
                except Exception:
                    pass
            if on_done:
                on_done()

        # 顺便清理已经自然结束但没被 pop 的进程句柄
        for wid, p in list(active.items()):
            if not p.is_alive():
                try:
                    p.join(timeout=0.5)
                except Exception:
                    pass
                # 进程结束但没发结果（异常退出），计为失败
                if not final:
                    active.pop(wid, None)
                    self.fail_count += 1
                    done += 1
                    self._log(0, f"[主进程] ⚠️ 任务 #{wid} 进程异常退出，计为失败")
                    if self.result_callback:
                        try:
                            self.result_callback(wid, {"ok": False, "error": "进程异常退出"})
                        except Exception:
                            pass

        return done

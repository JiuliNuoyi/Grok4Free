"""Grok4Free 精简版 Tkinter GUI。

包含：
- MoEmail 配置区（API Base / API Key / Domain）
- 代理开关
- 注册数量输入框
- 开始 / 停止按钮
- 实时日志滚动框
- 统计栏（成功 / 失败 / 进度）

完全独立，不依赖原项目 grok_register_ttk.py 的任何代码。
"""

import sys
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import queue
import os

# 版本号
__version__ = "v0.1.0"

# 导入后端模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import load_config, save_config, get_moemail_api_base, get_moemail_api_key, \
                         get_moemail_domain, get_proxy, get_proxies, get_mail_mode, \
                         get_msgraph_accounts, get_submailbox_accounts
from src.scheduler import RegistrationScheduler


class Grok4FreeGUI:
    """主窗口类。"""
    
    # 配色方案
    BG = "#f5f5f5"           # 主背景
    PANEL_BG = "#ffffff"     # 面板背景
    FG = "#333333"           # 前景色
    ACCENT = "#2196F3"       # 强调色（蓝色）
    SUCCESS = "#4CAF50"      # 成功绿色
    ERROR = "#f44336"        # 错误红色
    
    def __init__(self, root):
        self.root = root
        self.root.title(f"Grok4Free v{__version__} - 自动注册工具")
        self.root.geometry("1000x750")
        self.root.minsize(800, 600)
        
        # 状态标志
        self.running = False
        self.stop_requested = False
        self.ui_queue = queue.Queue()
        self._scheduler = None
        
        # 统计数据
        self.success_count = 0
        self.fail_count = 0
        
        # 加载配置
        self.cfg = load_config()
        
        # 初始化 UI
        self._setup_ui()
        
        # 启动 UI 队列处理
        self.root.after(50, self._process_ui_queue)
    
    def _setup_ui(self):
        """构建界面。"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部：标题
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(title_frame, text="Grok4Free", font=("Arial", 20, "bold")).pack(side=tk.LEFT)
        ttk.Label(title_frame, text="· Grok 账号自动注册工具", font=("Arial", 10)).pack(side=tk.LEFT, padx=(10, 0))
        
        # 左侧：配置区
        config_frame = ttk.LabelFrame(main_frame, text="配置", padding="10")
        config_frame.pack(side=tk.LEFT, fill=tk.Y, pady=(0, 10))
        
        self._create_config_widgets(config_frame)
        
        # 右侧主区域
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # 日志框
        log_frame = ttk.LabelFrame(right_frame, text="运行日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=20, wrap=tk.WORD, font=("Consolas", 9))
        scroll_x = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL, command=self.log_text.xview)
        scroll_y = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 底部控制区
        control_frame = ttk.Frame(right_frame)
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 按钮行
        btn_row = ttk.Frame(control_frame)
        btn_row.pack(fill=tk.X, pady=(0, 5))
        
        self.start_btn = ttk.Button(btn_row, text="开始注册", command=self._start_registration, width=12)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_btn = ttk.Button(btn_row, text="停止", command=self._stop_registration, width=12, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(btn_row, text="清空日志", command=self._clear_log, width=12).pack(side=tk.LEFT)
        
        # 新增：打开账号记录文件按钮
        ttk.Button(btn_row, text="查看账号记录", command=self._open_accounts_file, width=16).pack(side=tk.LEFT)
        
        # 统计栏
        self.stats_var = tk.StringVar(value="就绪")
        ttk.Label(control_frame, textvariable=self.stats_var, font=("Arial", 10, "bold"),
                  foreground="#2196F3").pack(anchor=tk.W)
    
    def _create_config_widgets(self, parent):
        """创建配置控件。"""
        # 邮箱模式选择（MoEmail / MS Graph 正常微软邮箱 / 子邮箱）
        ttk.Label(parent, text="邮箱模式:").pack(anchor=tk.W, pady=(10, 0))
        _mode = get_mail_mode(self.cfg)
        self._mode_label_to_key = {
            "MoEmail（自动创建临时邮箱）": "moemail",
            "MS Graph（自备微软邮箱）": "msgraph",
            "子邮箱（微软主邮箱生成）": "submailbox",
        }
        self._mode_key_to_label = {v: k for k, v in self._mode_label_to_key.items()}
        self.mail_mode_var = tk.StringVar(value=self._mode_key_to_label.get(_mode, "MoEmail（自动创建临时邮箱）"))
        mode_combo = ttk.Combobox(
            parent, textvariable=self.mail_mode_var, state="readonly", width=28,
            values=list(self._mode_label_to_key.keys()),
        )
        mode_combo.pack(fill=tk.X, pady=(0, 10))
        mode_combo.bind("<<ComboboxSelected>>", lambda e: self._on_mode_change())

        # 模式专属配置容器（固定在代理区之上，内部按模式显隐子 frame）
        self.mode_container = ttk.Frame(parent)
        self.mode_container.pack(fill=tk.X)

        # ===== MoEmail 配置区（可显隐）=====
        self.moemail_frame = ttk.Frame(self.mode_container)
        mp = self.moemail_frame

        # MoEmail API Base
        ttk.Label(mp, text="API Base:").pack(anchor=tk.W, pady=(0, 0))
        self.api_base_var = tk.StringVar(value=get_moemail_api_base(self.cfg))
        api_base_entry = ttk.Entry(mp, textvariable=self.api_base_var, width=30)
        api_base_entry.pack(fill=tk.X, pady=(0, 15))
        
        # MoEmail API Key
        ttk.Label(mp, text="API Key:").pack(anchor=tk.W)
        self.api_key_var = tk.StringVar(value=get_moemail_api_key(self.cfg))
        api_key_entry = ttk.Entry(mp, textvariable=self.api_key_var, show="*", width=30)
        api_key_entry.pack(fill=tk.X, pady=(0, 15))
        
        # MoEmail Domain
        ttk.Label(mp, text="Domain (@符号可省略):").pack(anchor=tk.W, pady=(10, 0))
        self.domain_var = tk.StringVar(value=get_moemail_domain(self.cfg))
        domain_entry = ttk.Entry(mp, textvariable=self.domain_var, width=30)
        domain_entry.pack(fill=tk.X, pady=(0, 15))

        # 注册数量（仅 MoEmail 模式有意义，放在 MoEmail 区内）
        ttk.Label(mp, text="注册数量:").pack(anchor=tk.W, pady=(10, 0))
        count_val = self.cfg.get("register_count", 1)
        self.count_var = tk.StringVar(value=str(max(count_val, 1)))
        count_entry = ttk.Spinbox(mp, from_=1, to=99, textvariable=self.count_var, width=12)
        count_entry.pack(pady=(0, 15))

        # ===== MS Graph 配置区（可显隐）=====
        self.msgraph_frame = ttk.Frame(self.mode_container)
        gp = self.msgraph_frame
        gp_head = ttk.Frame(gp)
        gp_head.pack(fill=tk.X, pady=(0, 0))
        ttk.Label(gp_head, text="微软邮箱账号 (一行一个):").pack(side=tk.LEFT)
        ttk.Button(gp_head, text="清除", width=6,
                   command=lambda: self._clear_accounts(self.msgraph_text, "微软邮箱")
                   ).pack(side=tk.RIGHT)
        self.msgraph_text = tk.Text(gp, width=30, height=8, font=("Consolas", 9), wrap=tk.NONE)
        self.msgraph_text.pack(fill=tk.X, pady=(0, 2))
        _init_accts = get_msgraph_accounts(self.cfg)
        if _init_accts:
            self.msgraph_text.insert("1.0", "\n".join(_init_accts))
        ttk.Label(gp, text="格式: 邮箱----密码----refresh_token----client_id",
                  font=("Arial", 8), foreground="#888888").pack(anchor=tk.W, pady=(0, 1))
        ttk.Label(gp, text="有几个邮箱就注册几个（数量=行数）",
                  font=("Arial", 8), foreground="#888888").pack(anchor=tk.W, pady=(0, 15))

        # ===== 子邮箱配置区（可显隐）=====
        self.submailbox_frame = ttk.Frame(self.mode_container)
        sp = self.submailbox_frame
        sp_head = ttk.Frame(sp)
        sp_head.pack(fill=tk.X, pady=(0, 0))
        ttk.Label(sp_head, text="子邮箱账号 (一行一个):").pack(side=tk.LEFT)
        ttk.Button(sp_head, text="清除", width=6,
                   command=lambda: self._clear_accounts(self.submailbox_text, "子邮箱")
                   ).pack(side=tk.RIGHT)
        self.submailbox_text = tk.Text(sp, width=30, height=8, font=("Consolas", 9), wrap=tk.NONE)
        self.submailbox_text.pack(fill=tk.X, pady=(0, 2))
        _init_sub = get_submailbox_accounts(self.cfg)
        if _init_sub:
            self.submailbox_text.insert("1.0", "\n".join(_init_sub))
        ttk.Label(sp, text="格式: 邮箱----密码----令牌----client_id",
                  font=("Arial", 8), foreground="#888888").pack(anchor=tk.W, pady=(0, 1))
        ttk.Label(sp, text="微软主邮箱生成，共享收件系统，按收件地址取件",
                  font=("Arial", 8), foreground="#888888").pack(anchor=tk.W, pady=(0, 1))
        ttk.Label(sp, text="有几个子邮箱就注册几个（数量=行数）",
                  font=("Arial", 8), foreground="#888888").pack(anchor=tk.W, pady=(0, 15))

        # ===== 通用配置区（代理 + 并发，始终显示）=====
        # Proxy（多行，一行一个；每个进程分配不同代理以规避风控）
        ttk.Label(parent, text="代理 (可留空，一行一个):").pack(anchor=tk.W, pady=(10, 0))
        self.proxy_text = tk.Text(parent, width=30, height=5, font=("Consolas", 9), wrap=tk.NONE)
        self.proxy_text.pack(fill=tk.X, pady=(0, 2))
        # 载入已有代理（优先多行 proxies，回退单个 proxy）
        _init_proxies = get_proxies(self.cfg)
        if _init_proxies:
            self.proxy_text.insert("1.0", "\n".join(_init_proxies))
        ttk.Label(parent, text="格式: http://user:pass@host:port",
                  font=("Arial", 8), foreground="#888888").pack(anchor=tk.W, pady=(0, 1))
        ttk.Label(parent, text="多个代理时每进程分配不同代理，规避风控",
                  font=("Arial", 8), foreground="#888888").pack(anchor=tk.W, pady=(0, 15))

        # Concurrency（并发数，1-5）
        ttk.Label(parent, text="并发数 (1-5):").pack(anchor=tk.W, pady=(10, 0))
        conc_val = self.cfg.get("concurrency", 1)
        try:
            conc_val = max(1, min(int(conc_val), 5))
        except (ValueError, TypeError):
            conc_val = 1
        self.concurrency_var = tk.StringVar(value=str(conc_val))
        conc_entry = ttk.Spinbox(parent, from_=1, to=5, textvariable=self.concurrency_var, width=12)
        conc_entry.pack(pady=(0, 2))
        ttk.Label(parent, text="同时打开的浏览器窗口数",
                  font=("Arial", 8), foreground="#888888").pack(anchor=tk.W, pady=(0, 2))
        ttk.Label(parent, text="推荐 1 并发，多并发注册容易风控",
                  font=("Arial", 8), foreground="#f44336").pack(anchor=tk.W, pady=(0, 15))
        
        # Save Button
        ttk.Button(parent, text="保存配置", command=self._save_config).pack(pady=(0, 10))

        # 根据当前模式显隐对应配置区
        self._on_mode_change()

    def _current_mail_mode(self):
        """返回当前选中的邮箱模式 key（moemail / msgraph）。"""
        return self._mode_label_to_key.get(self.mail_mode_var.get(), "moemail")

    def _on_mode_change(self):
        """切换邮箱模式时显隐对应的配置区。"""
        mode = self._current_mail_mode()
        self.moemail_frame.pack_forget()
        self.msgraph_frame.pack_forget()
        self.submailbox_frame.pack_forget()
        if mode == "msgraph":
            self.msgraph_frame.pack(fill=tk.X)
        elif mode == "submailbox":
            self.submailbox_frame.pack(fill=tk.X)
        else:
            self.moemail_frame.pack(fill=tk.X)

    def _read_msgraph_accounts(self):
        """从多行文本框读取正常微软邮箱账号（去空、去重、保持顺序）。"""
        return self._read_text_lines(self.msgraph_text)

    def _read_submailbox_accounts(self):
        """从多行文本框读取子邮箱账号（去空、去重、保持顺序）。"""
        return self._read_text_lines(self.submailbox_text)

    def _read_text_lines(self, text_widget):
        raw = text_widget.get("1.0", tk.END)
        seen = set()
        result = []
        for line in raw.replace("\r", "\n").split("\n"):
            item = line.strip()
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    def _clear_accounts(self, text_widget, label):
        """一键清除邮箱账号输入框（需确认）。"""
        content = text_widget.get("1.0", tk.END).strip()
        if not content:
            self._log(f"[*] {label}账号输入框已是空的")
            return
        if not messagebox.askyesno("确认清除", f"确定清空所有{label}账号吗？此操作不可撤销。"):
            return
        text_widget.delete("1.0", tk.END)
        self._log(f"[*] 已清除{label}账号输入框")

    
    def _log(self, message):
        """向日志框写入消息（线程安全）。"""
        timestamp = self._get_timestamp()
        line = f"[{timestamp}] {message}\n"
        self.ui_queue.put(("log", line))
    
    def _get_timestamp(self):
        """获取时间戳字符串。"""
        try:
            import datetime
            return datetime.datetime.now().strftime("%H:%M:%S")
        except Exception:
            return ""
    
    def _process_ui_queue(self):
        """处理 UI 队列中的事件。"""
        try:
            while True:
                event = self.ui_queue.get_nowait()
                kind = event[0]
                
                if kind == "log":
                    line = event[1]
                    self.log_text.insert(tk.END, line)
                    self.log_text.see(tk.END)
                    
                elif kind == "clear_log":
                    self.log_text.delete(1.0, tk.END)
                    
                elif kind == "stats":
                    success, fail, total = event[1], event[2], event[3]
                    status = f"成功：{success} | 失败：{fail} | 总数：{total}"
                    self.root.after(0, lambda s=status: self.stats_var.set(s))
                    
                elif kind == "running":
                    running = event[1]
                    self.root.after(0, lambda r=running: self._update_buttons(running=r))
                    
        except queue.Empty:
            pass
        except Exception as e:
            print(f"[!] UI 队列处理异常：{e}")
        
        # 持续监听
        self.root.after(100, self._process_ui_queue)
    
    def _update_buttons(self, running):
        """更新按钮状态。"""
        self.start_btn.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if running else tk.DISABLED)
        self.running = running
    
    def _save_config(self):
        """保存配置到 config.json。"""
        try:
            cfg = load_config()
            cfg["moemail_api_base"] = self.api_base_var.get().strip().rstrip("/")
            cfg["moemail_api_key"] = self.api_key_var.get().strip()
            cfg["moemail_domain"] = self.domain_var.get().strip().lstrip("@")
            cfg["mail_mode"] = self._current_mail_mode()
            cfg["msgraph_accounts"] = self._read_msgraph_accounts()
            cfg["submailbox_accounts"] = self._read_submailbox_accounts()
            proxies = self._read_proxies()
            cfg["proxies"] = proxies
            cfg["proxy"] = proxies[0] if proxies else ""  # 兼容单代理字段
            cfg["concurrency"] = self._read_concurrency()

            save_config(cfg)
            
            # 更新本地引用
            self.cfg = cfg
            
            self._log("[✓] 配置已保存到 config.json")
            messagebox.showinfo("成功", "配置已保存！")
        except Exception as e:
            self._log(f"[×] 保存配置失败：{e}")
            messagebox.showerror("错误", f"保存配置失败：{e}")
    
    def _clear_log(self):
        """清空日志。"""
        self.ui_queue.put(("clear_log", None))
        self.success_count = 0
        self.fail_count = 0
        self.ui_queue.put(("stats", 0, 0, 0))
        self._log("[*] 日志已清空")
    
    def _open_accounts_file(self):
        """打开账号记录文件。"""
        import glob
        import os
        
        # 查找最新的账号记录文件
        files = glob.glob("accounts_*.txt")
        if not files:
            messagebox.showinfo("提示", "尚未找到任何账号记录文件。
请完成注册后查看。")
            return
        
        # 按修改时间排序，获取最新的文件
        latest_file = max(files, key=os.path.getmtime)
        
        try:
            # 使用系统默认文本编辑器打开
            if sys.platform.startswith('win'):
                os.startfile(latest_file)
            elif sys.platform.startswith('darwin'):
                os.system(f'open "{latest_file}"')
            else:
                # Linux - 尝试使用 xdg-open
                os.system(f'xdg-open "{latest_file}"')
            
            self._log(f"[*] 已打开账号记录：{latest_file}")
        except Exception as e:
            self._log(f"[×] 打开文件失败：{e}")
            messagebox.showerror("错误", f"无法打开文件：{e}")
    
    def _start_registration(self):
        """启动注册流程。"""
        mode = self._current_mail_mode()
        if mode in ("msgraph", "submailbox"):
            # 校验微软邮箱 / 子邮箱账号
            from src.mail_msgraph import parse_account_lines
            if mode == "submailbox":
                accounts_raw = self._read_submailbox_accounts()
                empty_msg = "请填写至少一个子邮箱账号"
                bad_msg = "子邮箱账号格式有误"
            else:
                accounts_raw = self._read_msgraph_accounts()
                empty_msg = "请填写至少一个微软邮箱账号"
                bad_msg = "微软邮箱账号格式有误"
            if not accounts_raw:
                messagebox.showerror("错误", empty_msg)
                return
            try:
                parse_account_lines("\n".join(accounts_raw))
            except Exception as e:
                messagebox.showerror("错误", f"{bad_msg}：{e}")
                return
        else:
            # 验证 MoEmail 配置
            api_base = self.api_base_var.get().strip()
            api_key = self.api_key_var.get().strip()
            domain = self.domain_var.get().strip()
            if not api_base or not api_key or not domain:
                messagebox.showerror("错误", "请完善 MoEmail 配置（API Base / API Key / Domain）")
                return
        
        self.stop_requested = False
        self._update_buttons(running=True)
        self._log("\n" + "=" * 60)
        self._log("[*] 开始 Camoufox 注册流程...")
        
        # 后台线程执行
        thread = threading.Thread(target=self._run_registration_thread, daemon=True)
        thread.start()
    
    def _read_concurrency(self):
        """读取并发数（1-5）。"""
        try:
            return max(1, min(int(self.concurrency_var.get().strip() or "1"), 5))
        except (ValueError, TypeError):
            return 1

    def _read_proxies(self):
        """从多行文本框读取代理列表（去空、去重、保持顺序）。"""
        raw = self.proxy_text.get("1.0", tk.END)
        seen = set()
        result = []
        for line in raw.replace("\r", "\n").split("\n"):
            item = line.strip()
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    def _run_registration_thread(self):
        """在后台线程中通过多进程调度器执行注册流程。"""
        try:
            # 更新配置并保存到磁盘（worker 子进程会从磁盘读取代理等）
            cfg = load_config()
            cfg["moemail_api_base"] = self.api_base_var.get().strip().rstrip("/")
            cfg["moemail_api_key"] = self.api_key_var.get().strip()
            cfg["moemail_domain"] = self.domain_var.get().strip().lstrip("@")
            proxies = self._read_proxies()
            cfg["proxies"] = proxies
            cfg["proxy"] = proxies[0] if proxies else ""  # 兼容单代理字段
            count_str = self.count_var.get().strip() or "1"
            try:
                count = max(int(count_str), 1)
            except ValueError:
                count = 1
            cfg["register_count"] = count
            concurrency = self._read_concurrency()
            cfg["concurrency"] = concurrency

            mode = self._current_mail_mode()
            cfg["mail_mode"] = mode
            graph_accounts = None
            if mode in ("msgraph", "submailbox"):
                from src.mail_msgraph import parse_account_lines
                if mode == "submailbox":
                    accounts_raw = self._read_submailbox_accounts()
                    cfg["submailbox_accounts"] = accounts_raw
                else:
                    accounts_raw = self._read_msgraph_accounts()
                    cfg["msgraph_accounts"] = accounts_raw
                graph_accounts = parse_account_lines("\n".join(accounts_raw))
                count = len(graph_accounts)  # 数量=邮箱数
                cfg["register_count"] = count

            save_config(cfg)

            if mode == "submailbox":
                self._log(f"[*] 子邮箱模式：{count} 个子邮箱，并发 {concurrency}（错峰启动）")
            elif mode == "msgraph":
                self._log(f"[*] MS Graph 模式：{count} 个微软邮箱，并发 {concurrency}（错峰启动）")
            else:
                self._log(f"[*] MoEmail 模式：总数 {count}，并发 {concurrency}（错峰启动）")

            # 统计
            last_stats = {"success": 0, "fail": 0}

            def result_callback(worker_id, result):
                if result.get("cancelled"):
                    return
                if result.get("ok"):
                    last_stats["success"] += 1
                    email = result.get("email", "unknown")
                    self._log(f"\n[✓] 任务 #{worker_id} 成功：{email}")
                else:
                    last_stats["fail"] += 1
                    error = result.get("error", "未知错误")
                    self._log(f"\n[×] 任务 #{worker_id} 失败：{error}")
                total = last_stats["success"] + last_stats["fail"]
                self.ui_queue.put(("stats", last_stats["success"], last_stats["fail"], total))

            def log_callback(worker_id, line):
                self._log(line)

            # 构建并运行调度器
            self._scheduler = RegistrationScheduler(
                config_dict=cfg,
                total=count,
                concurrency=concurrency,
                headless=False,  # 有头模式
                log_callback=log_callback,
                result_callback=result_callback,
                mail_mode=mode,
                graph_accounts=graph_accounts,
            )
            self._scheduler.run()

            self._log("\n[*] 注册流程执行完毕")

        except Exception as e:
            self._log(f"\n[×] 异常：{e}")
            import traceback
            self._log(traceback.format_exc())

        finally:
            self._scheduler = None
            self.ui_queue.put(("running", False))
            self._log("[*] 任务结束")

    def _stop_registration(self):
        """请求停止注册（通知所有 worker 进程）。"""
        self._log("\n[*] 请求停止注册...")
        self.stop_requested = True
        if getattr(self, "_scheduler", None) is not None:
            try:
                self._scheduler.request_stop()
            except Exception as e:
                self._log(f"[!] 停止调度器失败：{e}")


def main():
    """主入口。"""
    root = tk.Tk()
    app = Grok4FreeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

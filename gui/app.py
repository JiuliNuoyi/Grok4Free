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

# 导入后端模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import load_config, save_config, get_moemail_api_base, get_moemail_api_key, \
                         get_moemail_domain, get_proxy
from src.register import run_registration_flow


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
        self.root.title("Grok4Free - 自动注册工具")
        self.root.geometry("1000x750")
        self.root.minsize(800, 600)
        
        # 状态标志
        self.running = False
        self.stop_requested = False
        self.ui_queue = queue.Queue()
        
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
        
        # 统计栏
        stats_var = tk.StringVar(value="就绪")
        ttk.Label(control_frame, textvariable=stats_var, font=("Arial", 10, "bold"), 
                  foreground="#2196F3").pack(anchor=tk.W)
    
    def _create_config_widgets(self, parent):
        """创建配置控件。"""
        # MoEmail API Base
        ttk.Label(parent, text="API Base:").pack(anchor=tk.W, pady=(10, 0))
        self.api_base_var = tk.StringVar(value=get_moemail_api_base(self.cfg))
        api_base_entry = ttk.Entry(parent, textvariable=self.api_base_var, width=30)
        api_base_entry.pack(fill=tk.X, pady=(0, 15))
        
        # MoEmail API Key
        ttk.Label(parent, text="API Key:").pack(anchor=tk.W)
        self.api_key_var = tk.StringVar(value=get_moemail_api_key(self.cfg))
        api_key_entry = ttk.Entry(parent, textvariable=self.api_key_var, show="*", width=30)
        api_key_entry.pack(fill=tk.X, pady=(0, 15))
        
        # MoEmail Domain
        ttk.Label(parent, text="Domain (@符号可省略):").pack(anchor=tk.W, pady=(10, 0))
        self.domain_var = tk.StringVar(value=get_moemail_domain(self.cfg))
        domain_entry = ttk.Entry(parent, textvariable=self.domain_var, width=30)
        domain_entry.pack(fill=tk.X, pady=(0, 15))
        
        # Proxy
        ttk.Label(parent, text="代理 (可留空):").pack(anchor=tk.W, pady=(10, 0))
        self.proxy_var = tk.StringVar(value=get_proxy(self.cfg))
        proxy_entry = ttk.Entry(parent, textvariable=self.proxy_var, width=30)
        proxy_entry.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(parent, text="格式: http://user:pass@host:port",
                  font=("Arial", 8), foreground="#888888").pack(anchor=tk.W, pady=(0, 15))
        
        # Register Count
        ttk.Label(parent, text="注册数量:").pack(anchor=tk.W, pady=(10, 0))
        count_val = self.cfg.get("register_count", 1)
        self.count_var = tk.StringVar(value=str(max(count_val, 1)))
        count_entry = ttk.Spinbox(parent, from_=1, to=99, textvariable=self.count_var, width=12)
        count_entry.pack(pady=(0, 15))
        
        # Save Button
        ttk.Button(parent, text="保存配置", command=self._save_config).pack(pady=(0, 10))
    
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
            cfg["proxy"] = self.proxy_var.get().strip()
            
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
    
    def _start_registration(self):
        """启动注册流程。"""
        # 验证配置
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
    
    def _run_registration_thread(self):
        """在后台线程中执行注册流程。"""
        try:
            # 更新配置（保存到磁盘，因为 register 会从磁盘重新读取代理等）
            cfg = load_config()
            cfg["moemail_api_base"] = self.api_base_var.get().strip().rstrip("/")
            cfg["moemail_api_key"] = self.api_key_var.get().strip()
            cfg["moemail_domain"] = self.domain_var.get().strip().lstrip("@")
            cfg["proxy"] = self.proxy_var.get().strip()
            count_str = self.count_var.get().strip() or "1"
            try:
                count = max(int(count_str), 1)
            except ValueError:
                count = 1
            cfg["register_count"] = count
            save_config(cfg)
            
            # 定义 observer
            last_stats = {"success": 0, "fail": 0}
            
            def observer(result):
                last_stats["success"] += 1 if result.get("ok") else 0
                last_stats["fail"] += 1 if not result.get("ok") else 0
                total = last_stats["success"] + last_stats["fail"]
                
                self.ui_queue.put(("stats", last_stats["success"], last_stats["fail"], total))
                
                email = result.get("email", "unknown")
                if result.get("ok"):
                    self._log(f"\n[✓] 第{last_stats['success']}个账号成功：{email}")
                else:
                    error = result.get("error", "未知错误")
                    self._log(f"\n[×] 第{last_stats['fail']}个账号失败：{error}")
            
            # 调用注册流程
            run_registration_flow(
                log_callback=self._log,
                headless=False,  # 显示浏览器
                count=count,
                cancel_callback=lambda: self.stop_requested,
                observer=observer,
            )
            
            self._log("\n[*] 注册流程执行完毕")
            
        except Exception as e:
            self._log(f"\n[×] 异常：{e}")
            import traceback
            self._log(traceback.format_exc())
        
        finally:
            self.ui_queue.put(("running", False))
            self._log("[*] 任务结束")
    
    def _stop_registration(self):
        """请求停止注册。"""
        self._log("\n[*] 请求停止注册...")
        self.stop_requested = True


def main():
    """主入口。"""
    root = tk.Tk()
    app = Grok4FreeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Grok4Free CLI 入口。

用法:
    python run.py                # 启动 GUI
    python run.py register -n 1  # 命令行单次注册
    python run.py register -n 3 --headless  # 批量注册 3 个
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Grok4Free - Grok 账号自动注册工具")
    
    # 默认命令是 gui
    if not sys.argv[1:] or sys.argv[1] in ("gui", "--help"):
        from gui.app import main as run_gui
        
        print("\n" + "=" * 60)
        print("Grok4Free GUI 启动中...")
        print("=" * 60)
        
        try:
            run_gui()
        except KeyboardInterrupt:
            print("\n用户中断，退出")
        return 0
    
    # register 子命令
    parser.add_argument("command", nargs="?", default=None, help="命令：register（注册）或 gui（默认）")
    reg_parser = parser.add_argument_group("register 选项")
    reg_parser.add_argument("-n", "--count", type=int, default=1, help="注册数量（默认 1；msgraph 模式下由邮箱数量决定）")
    reg_parser.add_argument("-c", "--concurrency", type=int, default=1, help="并发进程数 1-5，错峰启动 (0.5-2s)（默认 1）")
    reg_parser.add_argument("-m", "--mail-mode", choices=["moemail", "msgraph", "submailbox"], default=None,
                            help="邮箱模式：moemail（自动创建）/ msgraph（正常微软邮箱）/ submailbox（子邮箱）。"
                                 "后两者读 config.json 的 msgraph_accounts / submailbox_accounts。默认沿用配置")
    reg_parser.add_argument("--headless", action="store_true", help="无头模式（不显示浏览器）")
    
    args = parser.parse_args()
    
    if args.command == "register":
        from src.config import (
            load_config, get_mail_mode, get_msgraph_accounts, get_submailbox_accounts,
        )

        cfg = load_config()
        mail_mode = args.mail_mode or get_mail_mode(cfg)

        graph_accounts = None
        count = max(args.count, 1)
        is_graph = mail_mode in ("msgraph", "submailbox")
        if is_graph:
            from src.mail_msgraph import parse_account_lines
            if mail_mode == "submailbox":
                accounts_raw = get_submailbox_accounts(cfg)
                field = "submailbox_accounts"
            else:
                accounts_raw = get_msgraph_accounts(cfg)
                field = "msgraph_accounts"
            if not accounts_raw:
                print(f"❌ {mail_mode} 模式下 config.json 的 {field} 为空，请先填写邮箱账号")
                return 1
            try:
                graph_accounts = parse_account_lines("\n".join(accounts_raw))
            except Exception as e:
                print(f"❌ 邮箱账号格式有误：{e}")
                return 1
            count = len(graph_accounts)  # 数量=邮箱数

        concurrency = max(1, min(args.concurrency, 5))
        if mail_mode == "submailbox":
            print(f"\n🚀 子邮箱模式：{count} 个子邮箱（并发 {concurrency}）...\n")
        elif mail_mode == "msgraph":
            print(f"\n🚀 MS Graph 模式：{count} 个微软邮箱（并发 {concurrency}）...\n")
        else:
            print(f"\n🚀 MoEmail 模式：注册 {count} 个账号（并发 {concurrency}）...\n")

        # 微软邮箱模式恒走调度器（需按邮箱派发账号）；moemail 模式并发>1 才走调度器
        if is_graph or concurrency > 1:
            # 多进程调度器
            from src.scheduler import RegistrationScheduler

            def _log(wid, line):
                print(line)

            def _result(wid, result):
                pass

            sched = RegistrationScheduler(
                config_dict=cfg,
                total=count,
                concurrency=concurrency,
                headless=args.headless,
                log_callback=_log,
                result_callback=_result,
                mail_mode=mail_mode,
                graph_accounts=graph_accounts,
            )
            success, fail, total = sched.run()
        else:
            # 单进程串行（MoEmail）
            from src.register import run_registration_flow

            success, fail, total = run_registration_flow(
                log_callback=None,
                headless=args.headless,
                count=count,
            )

        print(f"\n✅ 结束！成功：{success}, 失败：{fail}, 总数：{total}")
        return 0 if success == count else 1
    
    else:
        # 未知命令或默认 gui
        from gui.app import main as run_gui
        
        try:
            run_gui()
        except KeyboardInterrupt:
            pass
        return 0


if __name__ == "__main__":
    main()

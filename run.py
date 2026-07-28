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
    reg_parser.add_argument("-n", "--count", type=int, default=1, help="注册数量（默认 1）")
    reg_parser.add_argument("-c", "--concurrency", type=int, default=1, help="并发进程数 1-5（默认 1）")
    reg_parser.add_argument("--headless", action="store_true", help="无头模式（不显示浏览器）")
    
    args = parser.parse_args()
    
    if args.command == "register":
        count = max(args.count, 1)
        concurrency = max(1, min(args.concurrency, 5))
        print(f"\n🚀 开始注册 {count} 个账号（并发 {concurrency}）...\n")

        if concurrency > 1:
            # 多进程调度器
            from src.scheduler import RegistrationScheduler
            from src.config import load_config

            cfg = load_config()

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
            )
            success, fail, total = sched.run()
        else:
            # 单进程串行
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

#!/usr/bin/env python3
"""手动测试脚本：显示浏览器窗口让你手动点击授权页面。

适合第一次测试或调试使用。
"""

import sys
sys.path.insert(0, ".")
from src.register import run_registration_flow

print("=" * 60)
print("🎭 手动测试模式 - 浏览器会显示，请根据提示操作")
print("=" * 60)
print("\n⚠️ 注意:")
print("  1. 首次 OAuth 授权时会出现授权页面")
print("  2. 请手动点击 '允许/Allow' 按钮")
print("  3. 之后的所有步骤会自动完成")
print("  4. 如需随时停止，按 Ctrl+C")
print()

# headless=False 让浏览器显示出来
success, fail, total = run_registration_flow(
    log_callback=None,  # 终端实时显示日志
    headless=False,     # ✅ 关键：显示浏览器窗口
    count=1,            # 只跑 1 个账号测试
)

print(f"\n{'='*60}")
print(">>> 测试结果")
print(f"   成功：{success} | 失败：{fail} | 总数：{total}")

if success > 0:
    print("\n🎉 恭喜！注册和 OAuth 授权都成功了！")
else:
    print("\n⚠️ 遇到问题了，检查上面的日志")

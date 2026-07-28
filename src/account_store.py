"""账号存储：把成功注册的账号追加保存到文件。

替代原项目 account_outputs.py（400 行），只需要这一个 append 函数。
"""

import os


def append_account(path, email, password, refresh_token):
    """把账号追加保存到文件，格式：email----password----refresh_token。

    使用 flush + fsync 确保即时落盘（避免程序崩溃丢数据）。
    """
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{email}----{password}----{refresh_token}\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path

"""控制台编码兼容工具

Windows 控制台默认使用 GBK(cp936) 编码，输出中文或符号（✓、emoji）时会抛出
UnicodeEncodeError 或显示乱码。命令行入口启动时应先调用 ensure_utf8_console()。
"""

import sys


def ensure_utf8_console() -> bool:
    """尽最大努力把标准输出/标准错误切换为 UTF-8。

    返回是否全部成功；失败时保持静默，不影响主流程。
    """
    ok = True
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # 被重定向到不支持 reconfigure 的流
            ok = False
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            ok = False
    return ok

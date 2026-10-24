"""轻量 Prometheus 指标端点

仅依赖标准库，用于把引擎运行指标以 Prometheus 文本格式暴露在 /metrics 上，
供 deployments/prometheus.yml 抓取。默认不启动，需要时用 --metrics-port 开启。
"""

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict


def render_metrics(snapshot: Dict[str, float]) -> str:
    """把指标字典渲染成 Prometheus 文本格式（非数值项会被忽略）"""
    lines = []
    for name, value in sorted((snapshot or {}).items()):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        metric = name if name.startswith("autonews_") else f"autonews_{name}"
        lines.append(f"# TYPE {metric} gauge")
        lines.append(f"{metric} {float(value):g}")
    return "\n".join(lines) + "\n"


class _Handler(BaseHTTPRequestHandler):
    provider: Callable[[], Dict[str, float]] = staticmethod(dict)
    plugin_name = "autonews"

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler 规定的命名
        if self.path.split("?")[0] not in ("/metrics", "/"):
            self.send_response(404)
            self.end_headers()
            return

        body = self._render().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _render(self) -> str:
        try:
            snapshot = self.provider() or {}
        except Exception:  # 指标采集失败不应让抓取端 500
            snapshot = {}
        return render_metrics(snapshot)

    def log_message(self, fmt, *args):  # 静默访问日志
        return


class MetricsServer:
    """把 provider() 返回的数值以 Prometheus 格式暴露出去"""

    def __init__(self, provider: Callable[[], Dict[str, float]], port: int = 9090, host: str = "0.0.0.0"):
        self.provider = provider
        self.port = int(port)
        self.host = host
        self.logger = logging.getLogger(__name__)
        self._server = None
        self._thread = None

    def start(self) -> bool:
        if self._server is not None:
            return True

        handler = type("MetricsHandler", (_Handler,), {"provider": staticmethod(self.provider)})
        try:
            self._server = ThreadingHTTPServer((self.host, self.port), handler)
        except OSError as e:
            self.logger.warning(f"指标端点启动失败（端口 {self.port}）: {e}")
            self._server = None
            return False

        self._thread = threading.Thread(
            target=self._server.serve_forever, name="MetricsServer", daemon=True
        )
        self._thread.start()
        self.logger.info(f"指标端点已启动: http://{self.host}:{self.port}/metrics")
        return True

    def stop(self) -> None:
        if self._server is None:
            return
        try:
            self._server.shutdown()
            self._server.server_close()
        finally:
            self._server = None
            self._thread = None

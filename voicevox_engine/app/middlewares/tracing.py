"""リクエストトレーシングとパフォーマンスメトリクスのミドルウェア"""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from voicevox_engine.logging import logger


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    リクエストトレーシングミドルウェア

    各リクエストに一意のIDを割り当て、ログに記録します。
    リクエストの処理時間も計測してログに出力します。
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # リクエストIDを生成または取得
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # リクエスト開始時刻
        start_time = time.time()

        # リクエスト情報をログに記録
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_host": request.client.host if request.client else None,
            },
        )

        # リクエストを処理
        try:
            response = await call_next(request)
        except Exception as e:
            # 例外が発生した場合
            process_time = time.time() - start_time
            logger.error(
                f"Request failed",
                exc_info=e,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "process_time": f"{process_time:.3f}s",
                },
            )
            raise

        # 処理時間を計算
        process_time = time.time() - start_time

        # レスポンスヘッダーにリクエストIDと処理時間を追加
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.3f}"

        # リクエスト完了をログに記録
        logger.info(
            f"Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time": f"{process_time:.3f}s",
            },
        )

        return response


class PerformanceMetricsMiddleware(BaseHTTPMiddleware):
    """
    パフォーマンスメトリクスミドルウェア

    リクエストの処理時間が一定値を超えた場合に警告を出力します。
    本番環境では Prometheus などのメトリクスシステムと統合すべきです。
    """

    # 警告を出すしきい値（秒）
    SLOW_REQUEST_THRESHOLD = 1.0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        # 処理時間が長い場合は警告を出力
        if process_time > self.SLOW_REQUEST_THRESHOLD:
            logger.warning(
                f"Slow request detected",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "process_time": f"{process_time:.3f}s",
                    "threshold": f"{self.SLOW_REQUEST_THRESHOLD}s",
                },
            )

        # TODO: Prometheus などのメトリクスシステムに送信
        # prometheus_client.histogram.observe(process_time)

        return response

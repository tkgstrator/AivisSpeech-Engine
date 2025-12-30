"""Gunicorn 設定ファイル

本番環境で Gunicorn + Uvicorn Workers を使用する際の推奨設定
使用方法: gunicorn -c gunicorn_conf.py voicevox_engine.app.application:app
"""

import multiprocessing
import os

# ワーカー設定
# CPU コア数 * 2 + 1 を推奨（環境変数で上書き可能）
workers = int(os.getenv("VV_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"

# バインドアドレス
bind = os.getenv("VV_BIND", "0.0.0.0:10101")

# タイムアウト設定
timeout = int(os.getenv("VV_TIMEOUT", "120"))  # ワーカータイムアウト（秒）
keepalive = int(os.getenv("VV_KEEPALIVE", "5"))  # Keep-Alive 接続のタイムアウト
graceful_timeout = int(os.getenv("VV_GRACEFUL_TIMEOUT", "30"))  # グレースフルシャットダウン時間

# ログ設定
accesslog = os.getenv("VV_ACCESS_LOG", "-")  # アクセスログ ("-" は stdout)
errorlog = os.getenv("VV_ERROR_LOG", "-")  # エラーログ
loglevel = os.getenv("VV_LOG_LEVEL", "info")  # ログレベル

# プロセス名
proc_name = "aivisspeech-engine"

# プリロード設定（メモリ効率化）
preload_app = True

# 最大リクエスト数（メモリリーク対策）
max_requests = int(os.getenv("VV_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("VV_MAX_REQUESTS_JITTER", "50"))

# ワーカー接続数制限
worker_connections = int(os.getenv("VV_WORKER_CONNECTIONS", "1000"))

# Uvicorn 固有の設定（環境変数経由）
# これらは UvicornWorker に渡される
raw_env = [
    f"UVICORN_LIMIT_CONCURRENCY={os.getenv('VV_LIMIT_CONCURRENCY', '100')}",
    f"UVICORN_TIMEOUT_KEEP_ALIVE={os.getenv('VV_TIMEOUT_KEEP_ALIVE', '5')}",
]


def on_starting(server):
    """サーバー起動時のフック"""
    server.log.info(f"Starting Gunicorn with {workers} workers")


def on_reload(server):
    """リロード時のフック"""
    server.log.info("Reloading Gunicorn")


def worker_int(worker):
    """ワーカー中断時のフック"""
    worker.log.info(f"Worker {worker.pid} received INT or QUIT signal")


def worker_abort(worker):
    """ワーカー異常終了時のフック"""
    worker.log.error(f"Worker {worker.pid} received SIGABRT signal")

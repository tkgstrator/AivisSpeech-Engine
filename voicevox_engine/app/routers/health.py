"""ヘルスチェックとメトリクスのルーター"""

from typing import Any

from fastapi import APIRouter, Response, status

from voicevox_engine import __version__

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="ヘルスチェック",
    responses={
        200: {
            "description": "正常稼働中",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "version": "1.0.0",
                    }
                }
            },
        }
    },
)
def health_check() -> dict[str, Any]:
    """
    基本的なヘルスチェックエンドポイント

    サービスが稼働していることを確認します。
    ロードバランサーやモニタリングツールから定期的に呼び出されます。
    """
    return {
        "status": "healthy",
        "version": __version__,
    }


@router.get(
    "/health/ready",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Readiness チェック",
    responses={
        200: {
            "description": "リクエスト受付可能",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ready",
                        "version": "1.0.0",
                    }
                }
            },
        },
        503: {
            "description": "リクエスト受付不可（起動中または停止中）",
        },
    },
)
def readiness_check() -> dict[str, Any]:
    """
    Readiness チェックエンドポイント

    サービスがリクエストを受け付けられる状態かを確認します。
    Kubernetes の readinessProbe などで使用されます。

    起動中やシャットダウン中は 503 を返すべきですが、
    現在の実装では常に ready を返します。
    """
    # TODO: モデルロード状態などを確認して適切なステータスを返す
    return {
        "status": "ready",
        "version": __version__,
    }


@router.get(
    "/health/live",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Liveness チェック",
    responses={
        200: {
            "description": "プロセス稼働中",
            "content": {
                "application/json": {
                    "example": {
                        "status": "alive",
                        "version": "1.0.0",
                    }
                }
            },
        }
    },
)
def liveness_check() -> dict[str, Any]:
    """
    Liveness チェックエンドポイント

    プロセスが生存しているかを確認します。
    Kubernetes の livenessProbe などで使用されます。

    このエンドポイントが応答しない場合、コンテナは再起動されます。
    """
    return {
        "status": "alive",
        "version": __version__,
    }


@router.get(
    "/metrics",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="メトリクス取得",
    responses={
        200: {
            "description": "Prometheus 形式のメトリクス",
            "content": {
                "text/plain": {
                    "example": "# HELP aivis_engine_info Engine information\n# TYPE aivis_engine_info gauge\naivis_engine_info{version=\"1.0.0\"} 1\n"
                }
            },
        }
    },
)
def metrics() -> Response:
    """
    Prometheus 形式のメトリクスエンドポイント

    現在は基本的な情報のみを返します。
    本番環境では prometheus_client などを使用して、
    リクエスト数、レスポンスタイム、エラー率などを追加すべきです。
    """
    # TODO: prometheus_client を使用して実際のメトリクスを収集・公開
    metrics_text = f"""# HELP aivis_engine_info Engine information
# TYPE aivis_engine_info gauge
aivis_engine_info{{version="{__version__}"}} 1

# HELP aivis_engine_build_info A metric with a constant '1' value labeled by version
# TYPE aivis_engine_build_info gauge
aivis_engine_build_info{{version="{__version__}"}} 1
"""
    return Response(content=metrics_text, media_type="text/plain; version=0.0.4")

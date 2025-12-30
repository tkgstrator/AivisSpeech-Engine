ARG CUDA_VERSION=12.8.1

# ===== ステージ1: ビルドステージ =====
FROM nvidia/cuda:${CUDA_VERSION}runtime-ubuntu22.04 AS builder

# ビルドに必要な依存関係をインストール
RUN \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y \
    git \
    curl \
    build-essential

# Rust をインストール
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
    /root/.cargo/bin/rustup default stable
ENV PATH="/root/.cargo/bin:${PATH}"

# uv をインストールして Python 依存関係を解決
COPY --from=ghcr.io/astral-sh/uv:0.9.20 /uv /uvx /bin/
WORKDIR /opt

# 依存関係ファイルのみをコピーして依存関係をインストール
# これにより、ソースコードの変更時に依存関係のキャッシュが無効化されない
# UV_PYTHON_INSTALL_DIR を設定して Python を /opt/python にインストール
ENV UV_PYTHON_INSTALL_DIR=/opt/python
RUN \
    --mount=type=bind,source=uv.lock,target=uv.lock,readonly \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml,readonly \
    uv sync --python 3.11 --frozen

# ===== ステージ2: 本番実行ステージ =====
FROM nvidia/cuda:13.1.0-runtime-ubuntu22.04

# 本番環境に必要な最小限のパッケージのみをインストール
RUN \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl

# 非特権ユーザーを作成
RUN useradd -m -u 1000 -s /bin/bash user

WORKDIR /opt

# ビルドステージから Python と依存関係をコピー
COPY --from=builder --chown=user:user /opt/python /opt/python
COPY --from=builder --chown=user:user /opt/.venv /opt/.venv

# アプリケーションファイルをコピー
COPY --chown=user:user engine_manifest.json /opt/
COPY --chown=user:user run.py /opt/
COPY --chown=user:user app_factory.py /opt/
COPY --chown=user:user gunicorn_conf.py /opt/
COPY --chown=user:user resources /opt/resources
COPY --chown=user:user voicevox_engine /opt/voicevox_engine
COPY --chown=user:user .serena /opt/.serena
COPY --chown=user:user tools /opt/tools

# 非特権ユーザーに切り替え
USER user

# 環境変数を設定
ENV PATH="/opt/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ヘルスチェック（本番環境用）
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:10101/health || exit 1

# デフォルトコマンド（単一プロセス・開発用）
# 本番環境では docker-compose.yaml や Kubernetes マニフェストで上書きを推奨
CMD ["python", "run.py", "--use_gpu", "--host", "0.0.0.0", "--workers", "1"]

# 本番環境用の推奨起動コマンド（複数ワーカー）:
# CMD ["gunicorn", "-c", "gunicorn_conf.py", "app_factory:app"]

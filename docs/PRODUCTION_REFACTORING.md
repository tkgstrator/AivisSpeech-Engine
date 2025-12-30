# 本番環境対応リファクタリング完了

## 実装内容

AivisSpeech Engine を本番環境で大規模アクセスに耐えられるようリファクタリングしました。

## 主な変更点

### 1. 本番環境用設定の追加 (`run.py`)

- **環境変数とCLI引数の追加**:
  - `--workers`: ワーカープロセス数（デフォルト: 1、推奨: CPU コア数 × 2 + 1）
  - `--timeout-keep-alive`: Keep-Alive タイムアウト（秒）
  - `--timeout-graceful-shutdown`: グレースフルシャットダウン時間（秒）
  - `--limit-concurrency`: 同時リクエスト数の上限

- **Uvicorn の本番環境対応パラメータ**:
  - 複数ワーカーでの並列処理
  - タイムアウト設定
  - アクセスログの有効化

### 2. Gunicorn 統合 (`app_factory.py`, `gunicorn_conf.py`)

- **アプリケーションファクトリー** (`app_factory.py`):
  - Gunicorn から直接インポート可能
  - 環境変数で完全に設定可能
  - 起動時の初期化処理を分離

- **Gunicorn 設定ファイル** (`gunicorn_conf.py`):
  - ワーカー数の自動計算（CPU コア数 × 2 + 1）
  - タイムアウトとKeepalive設定
  - メモリリーク対策（max_requests）
  - プリロード機能でメモリ効率化

### 3. ヘルスチェックとメトリクス (`voicevox_engine/app/routers/health.py`)

- **エンドポイント**:
  - `GET /health`: 基本的なヘルスチェック
  - `GET /health/ready`: Readiness チェック（Kubernetes 用）
  - `GET /health/live`: Liveness チェック（Kubernetes 用）
  - `GET /metrics`: Prometheus 形式のメトリクス

### 4. リクエストトレーシング (`voicevox_engine/app/middlewares/tracing.py`)

- **RequestTracingMiddleware**:
  - リクエストIDの自動付与（X-Request-ID）
  - 処理時間の計測と記録（X-Process-Time）
  - 構造化ログ出力

- **PerformanceMetricsMiddleware**:
  - 処理時間の監視
  - 遅いリクエストの警告

### 5. Dockerfile の本番環境最適化

- **マルチステージビルド**:
  - ビルドステージと実行ステージを分離
  - イメージサイズの削減

- **セキュリティ強化**:
  - 非特権ユーザー（appuser）での実行
  - 最小限のパッケージのみインストール

- **ヘルスチェック組み込み**:
  - Docker レベルでのヘルスチェック

### 6. Docker Compose 設定更新 (`compose.yaml`)

- **開発環境用**:
  - 単一ワーカー
  - トレーシング無効

- **本番環境用**:
  - 複数ワーカー（Gunicorn）
  - リソース制限
  - ヘルスチェック
  - トレーシング有効

### 7. 依存関係の追加

- `gunicorn>=23.0.0,<24` を `pyproject.toml` に追加

### 8. ドキュメント作成

- **本番環境デプロイガイド** (`docs/本番環境デプロイガイド.md`):
  - デプロイ方法の詳細説明
  - パフォーマンスチューニングガイド
  - モニタリング設定
  - トラブルシューティング

## 使用方法

### 開発環境（従来通り）

```bash
# 単一プロセス
python run.py --use_gpu --host 0.0.0.0

# または Docker Compose
docker compose up aivis-dev
```

### 本番環境（複数ワーカー）

```bash
# 方法1: run.py で複数ワーカー
python run.py --use_gpu --host 0.0.0.0 --workers 9

# 方法2: Gunicorn で起動（推奨）
gunicorn -c gunicorn_conf.py app_factory:app

# 方法3: Docker Compose（推奨）
docker compose --profile production up -d aivis-prod
```

### 環境変数での設定

```bash
# ワーカー数
export VV_WORKERS=9

# タイムアウト
export VV_TIMEOUT=120
export VV_KEEPALIVE=5
export VV_GRACEFUL_TIMEOUT=30

# 同時リクエスト数制限
export VV_LIMIT_CONCURRENCY=100

# トレーシング有効化
export VV_ENABLE_TRACING=1

# 起動
python run.py --use_gpu --host 0.0.0.0
```

## パフォーマンス向上

- **単一プロセス（従来）**: 1リクエストずつ順次処理
- **複数ワーカー（本番）**: 同時に複数リクエストを並列処理
  - 4コアCPUの場合: 9ワーカー → 最大9倍のスループット
  - 8コアCPUの場合: 17ワーカー → 最大17倍のスループット

## 次のステップ

1. **依存関係の更新**:
   ```bash
   uv sync
   ```

2. **テスト**:
   ```bash
   # 開発環境でテスト
   docker compose up aivis-dev
   
   # 本番環境でテスト
   docker compose --profile production up aivis-prod
   ```

3. **ヘルスチェックの確認**:
   ```bash
   curl http://localhost:10101/health
   curl http://localhost:10101/health/ready
   curl http://localhost:10101/health/live
   curl http://localhost:10101/metrics
   ```

4. **負荷テスト**:
   - Apache Bench、wrk、Locust などで負荷テスト
   - ワーカー数とタイムアウトの調整

詳細は [docs/本番環境デプロイガイド.md](docs/本番環境デプロイガイド.md) を参照してください。

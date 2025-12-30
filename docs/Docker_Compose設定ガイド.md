# Docker Compose 設定ガイド

## 概要

AivisSpeech Engine を Docker で実行するための `compose.yaml` 設定について詳細に解説します。
開発環境と本番環境の両方に対応した設定を提供しています。

## ファイル構成

```
.
├── compose.yaml          # Docker Compose 設定ファイル
├── Dockerfile            # コンテナイメージのビルド設定
├── gunicorn_conf.py      # Gunicorn 本番環境設定
└── app_factory.py        # アプリケーションファクトリー
```

---

## 開発環境用サービス（aivis-dev）

開発やデバッグ用の単一ワーカー構成です。

```yaml
services:
  aivis-dev:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ./AivisSpeech-Engine-Dev:/home/appuser/.local/share/AivisSpeech-Engine-Dev
    ports:
      - "10101:10101"
    environment:
      - VV_WORKERS=1
      - VV_ENABLE_TRACING=0
    command: ["uv", "run", "python", "run.py", "--use_gpu", "--host", "0.0.0.0"]
```

### 起動方法

```bash
docker compose up aivis-dev
```

---

## 本番環境用サービス（aivis-prod）

大規模アクセスに対応するための複数ワーカー + Gunicorn 構成です。

```yaml
services:
  aivis-prod:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ./AivisSpeech-Engine-Dev:/home/appuser/.local/share/AivisSpeech-Engine-Dev
    ports:
      - "10101:10101"
    environment:
      # ワーカー数（CPU コア数 * 2 + 1 を推奨）
      - VV_WORKERS=5
      - VV_BIND=0.0.0.0:10101
      # タイムアウト設定
      - VV_TIMEOUT=120
      - VV_KEEPALIVE=5
      - VV_GRACEFUL_TIMEOUT=30
      # リクエスト制限
      - VV_LIMIT_CONCURRENCY=100
      - VV_MAX_REQUESTS=1000
      - VV_MAX_REQUESTS_JITTER=50
      # トレーシング有効化
      - VV_ENABLE_TRACING=1
      # GPU 使用
      - VV_USE_GPU=1
      - VV_LOAD_ALL_MODELS=0
      # CORS 設定
      - VV_CORS_POLICY_MODE=localapps
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:10101/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    command: ["uv", "run", "gunicorn", "-c", "gunicorn_conf.py", "app_factory:app"]
    profiles: ["production"]
```

### 起動方法

```bash
# 本番環境プロファイルを指定して起動
docker compose --profile production up -d aivis-prod
```

---

## 環境変数パラメータ詳細

### ワーカー設定

| 環境変数 | 説明 | デフォルト値 | 推奨値 |
|---------|------|------------|-------|
| `VV_WORKERS` | ワーカープロセス数 | `1` | `CPU コア数 × 2 + 1` |
| `VV_BIND` | バインドアドレスとポート | `0.0.0.0:10101` | - |

#### VV_WORKERS の詳細

ワーカー数は同時に処理できるリクエスト数に直結します。

**計算式**: `(CPU コア数 × 2) + 1`

| CPU コア数 | 推奨ワーカー数 | 最大同時処理数 |
|-----------|--------------|---------------|
| 2コア | 5 | 5リクエスト |
| 4コア | 9 | 9リクエスト |
| 8コア | 17 | 17リクエスト |
| 16コア | 33 | 33リクエスト |

**注意事項**:
- ワーカー数が多すぎるとメモリ不足やコンテキストスイッチのオーバーヘッドが発生
- GPU メモリが限られている場合はワーカー数を制限する必要あり
- 各ワーカーは独立したプロセスとして動作し、モデルを個別にロード

---

### タイムアウト設定

| 環境変数 | 説明 | デフォルト値 | 推奨値 |
|---------|------|------------|-------|
| `VV_TIMEOUT` | ワーカータイムアウト（秒） | `120` | `120〜300` |
| `VV_KEEPALIVE` | Keep-Alive 接続タイムアウト（秒） | `5` | `2〜5` |
| `VV_GRACEFUL_TIMEOUT` | グレースフルシャットダウン時間（秒） | `30` | `30〜60` |
| `VV_TIMEOUT_KEEP_ALIVE` | Uvicorn の Keep-Alive タイムアウト（秒） | `5` | `5` |
| `VV_TIMEOUT_GRACEFUL_SHUTDOWN` | Uvicorn のグレースフルシャットダウン時間（秒） | `30` | `30` |

#### VV_TIMEOUT の詳細

ワーカープロセスがリクエストを処理する最大時間です。

```
クライアント → リクエスト送信 → [VV_TIMEOUT 以内に応答必須] → レスポンス返却
```

**設定のポイント**:
- 長い音声の合成には時間がかかるため、短すぎると途中でタイムアウト
- 長すぎると、ハングしたワーカーがリソースを占有し続ける
- 音声合成の平均処理時間 + バッファ（30秒程度）を目安に設定

#### VV_KEEPALIVE の詳細

HTTP Keep-Alive 接続の維持時間です。

```
クライアント ←─ Keep-Alive 接続 ─→ サーバー
              [VV_KEEPALIVE 秒間維持]
```

**設定のポイント**:
- 短すぎると接続の再確立オーバーヘッドが増加
- 長すぎると同時接続数が増加しリソースを消費
- 通常は `2〜5秒` で十分

#### VV_GRACEFUL_TIMEOUT の詳細

シャットダウン時に既存リクエストの完了を待つ最大時間です。

```
SIGTERM 受信 → [VV_GRACEFUL_TIMEOUT 秒間待機] → 強制終了
               ↓
        既存リクエストの処理完了を待つ
```

**設定のポイント**:
- 短すぎると処理中のリクエストが中断される
- 長すぎるとデプロイが遅延
- 最も長い処理時間より少し長く設定

---

### リクエスト制限

| 環境変数 | 説明 | デフォルト値 | 推奨値 |
|---------|------|------------|-------|
| `VV_LIMIT_CONCURRENCY` | 同時リクエスト数の上限 | `100` | `50〜200` |
| `VV_MAX_REQUESTS` | ワーカーあたりの最大リクエスト数 | `1000` | `500〜2000` |
| `VV_MAX_REQUESTS_JITTER` | 最大リクエスト数のランダム変動幅 | `50` | `MAX_REQUESTS の 5%` |
| `VV_WORKER_CONNECTIONS` | ワーカーあたりの最大接続数 | `1000` | `1000` |

#### VV_LIMIT_CONCURRENCY の詳細

サーバー全体で同時に処理するリクエスト数の上限です。

```
リクエスト1 ─┐
リクエスト2 ─┤
リクエスト3 ─┼→ [VV_LIMIT_CONCURRENCY まで処理]
...         │
リクエストN ─┘
             ↓
        超過分は 503 Service Unavailable
```

**設定のポイント**:
- 低すぎると正常なリクエストも拒否される
- 高すぎるとサーバーが過負荷になる
- `ワーカー数 × 10〜20` を目安に設定

#### VV_MAX_REQUESTS の詳細

ワーカープロセスが再起動するまでに処理する最大リクエスト数です。
メモリリーク対策として重要です。

```
ワーカー起動 → リクエスト処理 × N回 → ワーカー再起動
                                    ↑
                          VV_MAX_REQUESTS 到達
```

**設定のポイント**:
- メモリリークを防ぐために定期的なワーカー再起動が有効
- 頻繁すぎる再起動はパフォーマンスに影響
- `500〜2000` が一般的

#### VV_MAX_REQUESTS_JITTER の詳細

ワーカーの再起動タイミングにランダム性を加えます。

```
ワーカー1: MAX_REQUESTS + random(0, JITTER) でリスタート
ワーカー2: MAX_REQUESTS + random(0, JITTER) でリスタート
ワーカー3: MAX_REQUESTS + random(0, JITTER) でリスタート
```

**目的**: 全ワーカーが同時に再起動することを防ぐ（サンダリングハード問題の回避）

---

### トレーシングとモニタリング

| 環境変数 | 説明 | デフォルト値 | 推奨値 |
|---------|------|------------|-------|
| `VV_ENABLE_TRACING` | リクエストトレーシングの有効化 | `0` | `1`（本番環境） |
| `VV_ACCESS_LOG` | アクセスログの出力先 | `-`（stdout） | `-` または ファイルパス |
| `VV_ERROR_LOG` | エラーログの出力先 | `-`（stdout） | `-` または ファイルパス |
| `VV_LOG_LEVEL` | ログレベル | `info` | `info` または `warning` |

#### VV_ENABLE_TRACING の詳細

`1` に設定すると以下の機能が有効になります：

1. **リクエストID の付与**
   - 各リクエストに一意の UUID を割り当て
   - `X-Request-ID` ヘッダーでレスポンスに含まれる
   - ログにも記録され、リクエストの追跡が容易に

2. **処理時間の計測**
   - `X-Process-Time` ヘッダーで処理時間を返却
   - 遅いリクエスト（1秒以上）は警告ログを出力

```
リクエスト → [X-Request-ID: abc-123] → 処理 → レスポンス
                                         ↓
                              ログ: "Request completed"
                                    request_id=abc-123
                                    process_time=0.543s
```

---

### アプリケーション設定

| 環境変数 | 説明 | デフォルト値 | 推奨値 |
|---------|------|------------|-------|
| `VV_USE_GPU` | GPU を使用するか | `0` | `1`（GPU 利用時） |
| `VV_LOAD_ALL_MODELS` | 起動時に全モデルをロード | `0` | `0`（オンデマンド） |
| `VV_DISABLE_MUTABLE_API` | 変更系 API を無効化 | `0` | `1`（本番環境） |
| `VV_CORS_POLICY_MODE` | CORS ポリシーモード | `localapps` | `localapps` |
| `VV_ALLOW_ORIGIN` | 許可するオリジン（スペース区切り） | なし | 必要に応じて設定 |
| `VV_SETTING_FILE` | 設定ファイルのパス | デフォルトパス | - |
| `VV_PRESET_FILE` | プリセットファイルのパス | デフォルトパス | - |

#### VV_USE_GPU の詳細

`1` に設定すると GPU を使用した推論が有効になります。

**注意事項**:
- NVIDIA GPU が必要
- Docker で使用する場合は `nvidia-docker` または `--gpus all` オプションが必要
- GPU メモリが限られている場合はワーカー数を制限

```yaml
# GPU を使用する場合の追加設定
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

#### VV_CORS_POLICY_MODE の詳細

CORS（Cross-Origin Resource Sharing）の許可モードを設定します。

| 値 | 説明 |
|---|------|
| `all` | すべてのオリジンを許可 |
| `localapps` | localhost、特定のアプリ、ブラウザ拡張のみ許可 |

**`localapps` で許可されるオリジン**:
- `app://.`（Electron アプリなど）
- `https://aivis-project.com`
- `https://hub.aivis-project.com`
- `https://aivm-generator.aivis-project.com`
- `localhost` 関連（`127.0.0.1`、`[::1]`）
- ブラウザ拡張（`chrome-extension://`、`moz-extension://` など）

---

## リソース制限（deploy.resources）

```yaml
deploy:
  resources:
    limits:
      cpus: '4'      # 最大 CPU コア数
      memory: 8G     # 最大メモリ
    reservations:
      cpus: '2'      # 予約 CPU コア数
      memory: 4G     # 予約メモリ
```

### limits（上限）

コンテナが使用できるリソースの**最大値**です。

| パラメータ | 説明 | 推奨値 |
|-----------|------|-------|
| `cpus` | 使用可能な最大 CPU コア数 | ホストの 50〜80% |
| `memory` | 使用可能な最大メモリ | 用途に応じて調整 |

### reservations（予約）

コンテナに**保証される**最小リソースです。

| パラメータ | 説明 | 推奨値 |
|-----------|------|-------|
| `cpus` | 保証される最小 CPU コア数 | limits の 50% |
| `memory` | 保証される最小メモリ | limits の 50% |

### メモリ使用量の目安

| ワーカー数 | 推奨メモリ |
|-----------|----------|
| 1 | 2〜4GB |
| 5 | 4〜8GB |
| 9 | 8〜16GB |
| 17 | 16〜32GB |

---

## ヘルスチェック設定（healthcheck）

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:10101/health"]
  interval: 30s       # チェック間隔
  timeout: 10s        # タイムアウト
  retries: 3          # 失敗許容回数
  start_period: 60s   # 起動猶予時間
```

### パラメータ詳細

| パラメータ | 説明 | 推奨値 |
|-----------|------|-------|
| `test` | 実行するヘルスチェックコマンド | `/health` エンドポイントへのリクエスト |
| `interval` | ヘルスチェックの実行間隔 | `30s`（頻繁すぎると負荷増加） |
| `timeout` | レスポンスのタイムアウト時間 | `10s` |
| `retries` | 失敗とみなすまでの連続失敗回数 | `3`（一時的な問題を許容） |
| `start_period` | 起動時のチェック除外期間 | `60s`（モデルロード時間を考慮） |

### ヘルスチェックの状態

```
starting → healthy → unhealthy
    ↑          ↓          ↓
    └──────────┴──────────┘
         retries 回失敗で遷移
```

| 状態 | 説明 |
|-----|------|
| `starting` | 起動中（start_period 内） |
| `healthy` | 正常稼働中 |
| `unhealthy` | 異常検出（retries 回連続失敗） |

---

## プロファイル（profiles）

```yaml
profiles: ["production"]
```

プロファイルを使用することで、サービスをグループ化できます。

### 使用方法

```bash
# 開発環境（プロファイルなし）
docker compose up aivis-dev

# 本番環境（production プロファイル指定）
docker compose --profile production up aivis-prod

# 両方を起動
docker compose --profile production up
```

---

## ボリューム設定

```yaml
volumes:
  - ./AivisSpeech-Engine-Dev:/home/appuser/.local/share/AivisSpeech-Engine-Dev
```

### マウントされるデータ

| ホスト側 | コンテナ側 | 内容 |
|---------|-----------|------|
| `./AivisSpeech-Engine-Dev` | `/home/appuser/.local/share/AivisSpeech-Engine-Dev` | ユーザーデータ、モデル、設定ファイル |

### 本番環境での推奨設定

```yaml
volumes:
  # 名前付きボリュームを使用（パフォーマンス向上）
  - aivis-data:/home/appuser/.local/share/AivisSpeech-Engine-Dev

volumes:
  aivis-data:
    driver: local
```

---

## 本番環境用 compose.yaml 完全版

```yaml
services:
  aivis-prod:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - aivis-data:/home/appuser/.local/share/AivisSpeech-Engine-Dev
    ports:
      - "10101:10101"
    environment:
      # ワーカー設定
      - VV_WORKERS=9                    # 4コア CPU の場合
      - VV_BIND=0.0.0.0:10101
      
      # タイムアウト設定
      - VV_TIMEOUT=180                  # 3分
      - VV_KEEPALIVE=5
      - VV_GRACEFUL_TIMEOUT=30
      
      # リクエスト制限
      - VV_LIMIT_CONCURRENCY=100
      - VV_MAX_REQUESTS=1000
      - VV_MAX_REQUESTS_JITTER=50
      
      # モニタリング
      - VV_ENABLE_TRACING=1
      - VV_LOG_LEVEL=info
      
      # アプリケーション設定
      - VV_USE_GPU=1
      - VV_LOAD_ALL_MODELS=0
      - VV_DISABLE_MUTABLE_API=1        # 変更系 API を無効化
      - VV_CORS_POLICY_MODE=localapps
    
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:10101/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    
    restart: unless-stopped
    
    command: ["uv", "run", "gunicorn", "-c", "gunicorn_conf.py", "app_factory:app"]

volumes:
  aivis-data:
    driver: local
```

---

## トラブルシューティング

### ワーカーが頻繁にタイムアウトする

```bash
# タイムアウト値を増やす
- VV_TIMEOUT=300
```

### メモリ不足エラー

```bash
# ワーカー数を減らす
- VV_WORKERS=3

# メモリ制限を増やす
limits:
  memory: 16G
```

### 接続が拒否される

```bash
# 同時接続数制限を確認
- VV_LIMIT_CONCURRENCY=200

# ワーカー接続数を確認
- VV_WORKER_CONNECTIONS=2000
```

### GPU が認識されない

```yaml
# GPU リソースの予約を追加
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

---

## 関連ドキュメント

- [本番環境デプロイガイド](本番環境デプロイガイド.md) - 詳細なデプロイ手順
- [パッケージ切り替え](パッケージ切り替え.md) - Poetry から uv への移行について

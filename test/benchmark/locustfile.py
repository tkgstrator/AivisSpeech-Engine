"""
負荷テスト用 Locust ファイル

ステージング環境と本番環境のパフォーマンス比較に使用
/audio_query → /synthesis の一連のフローを実行

使用方法:
  # ベンチマークプロファイルで起動
  docker compose --profile benchmark up --build

  # ブラウザで http://localhost:8089 にアクセス
  # ステージング: http://aivis-staging:10101
  # 本番: http://aivis-prod:10101
"""

from locust import HttpUser, task, between

from test_texts import TEST_TEXTS


class SynthesisUser(HttpUser):
    """音声合成フロー（audio_query → synthesis）の負荷テストユーザー"""

    wait_time = between(0.5, 2)  # リクエスト間隔

    # テスト用のスピーカーID
    SPEAKER_ID = 888753760

    def on_start(self):
        """テスト開始時にスピーカーを初期化"""
        self.client.post(
            "/initialize_speaker",
            params={"speaker": self.SPEAKER_ID},
            name="/initialize_speaker"
        )
        self.text_index = 0

    def get_next_text(self):
        """テキストをローテーションで取得"""
        text = TEST_TEXTS[self.text_index % len(TEST_TEXTS)]
        self.text_index += 1
        return text

    @task
    def audio_query_and_synthesis(self):
        """audio_query → synthesis の一連のフローを実行"""
        text = self.get_next_text()

        # 1. audio_query: 音声クエリ生成
        with self.client.post(
            "/audio_query",
            params={"text": text, "speaker": self.SPEAKER_ID},
            name="/audio_query",
            catch_response=True
        ) as query_response:
            if query_response.status_code != 200:
                query_response.failure(f"audio_query failed: {query_response.status_code}")
                return

            audio_query = query_response.json()

        # 2. synthesis: 音声合成
        with self.client.post(
            "/synthesis",
            params={"speaker": self.SPEAKER_ID},
            json=audio_query,
            name="/synthesis",
            catch_response=True
        ) as synth_response:
            if synth_response.status_code != 200:
                synth_response.failure(f"synthesis failed: {synth_response.status_code}")
            elif synth_response.headers.get("content-type") != "audio/wav":
                synth_response.failure(f"unexpected content-type: {synth_response.headers.get('content-type')}")


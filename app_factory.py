"""アプリケーションファクトリーモジュール

Gunicorn や他の WSGI/ASGI サーバーから直接インポートして使用可能
"""

import gc
import os
from pathlib import Path

# truststore を適用
# fmt: off
import truststore  # isort: skip
truststore.inject_into_ssl()
# fmt: on

from voicevox_engine import __version__
from voicevox_engine.aivm_manager import AivmManager
from voicevox_engine.app.application import generate_app
from voicevox_engine.cancellable_engine import CancellableEngine
from voicevox_engine.core.core_initializer import MOCK_VER, initialize_cores
from voicevox_engine.engine_manifest import load_manifest
from voicevox_engine.library.library_manager import LibraryManager
from voicevox_engine.logging import logger
from voicevox_engine.preset.preset_manager import PresetManager
from voicevox_engine.setting.model import CorsPolicyMode
from voicevox_engine.setting.setting_manager import USER_SETTING_PATH, SettingHandler
from voicevox_engine.tts_pipeline.song_engine import make_song_engines_from_cores
from voicevox_engine.tts_pipeline.tts_engine import TTSEngineManager
from voicevox_engine.user_dict.user_dict_manager import UserDictionary
from voicevox_engine.utility.path_utility import (
    engine_manifest_path,
    engine_root,
    get_save_dir,
)


def create_app():
    """
    FastAPI アプリケーションを生成して返す

    Gunicorn などの ASGI サーバーから直接呼び出し可能
    環境変数で設定を制御:
        - VV_USE_GPU: GPU を使用するか (0/1)
        - VV_LOAD_ALL_MODELS: 起動時に全モデルを読み込むか (0/1)
        - VV_CORS_POLICY_MODE: CORS ポリシーモード (all/localapps)
        - VV_ALLOW_ORIGIN: 許可するオリジン（スペース区切り）
        - VV_DISABLE_MUTABLE_API: ミュータブル API を無効化 (0/1)
    """
    logger.info(f"Creating AivisSpeech Engine application (version {__version__})")

    # 環境変数から設定を読み込み
    use_gpu = os.getenv("VV_USE_GPU", "0") == "1"
    load_all_models = os.getenv("VV_LOAD_ALL_MODELS", "0") == "1"
    disable_mutable_api = os.getenv("VV_DISABLE_MUTABLE_API", "0") == "1"

    # AivmManager を初期化
    aivm_manager = AivmManager(get_save_dir() / "Models")

    # ごく稀に style_bert_vits2_tts_engine.py (が依存する onnxruntime) のインポート自体に失敗し
    # 例外が発生する環境があるようなので、例外をキャッチしてエラーログに出力できるよう、敢えてルーター初期化時にインポートする
    from voicevox_engine.tts_pipeline.style_bert_vits2_tts_engine import (
        StyleBertVITS2TTSEngine,
    )

    # TTS エンジンを初期化
    tts_engines = TTSEngineManager()
    tts_engines.register_engine(
        StyleBertVITS2TTSEngine(aivm_manager, use_gpu, load_all_models),
        MOCK_VER,
    )

    # コアを初期化
    core_manager = initialize_cores(
        use_gpu=use_gpu,
        voicelib_dirs=None,
        voicevox_dir=None,
        runtime_dirs=None,
        cpu_num_threads=4,
        enable_mock=True,
        load_all_models=load_all_models,
    )

    song_engines = make_song_engines_from_cores(core_manager)
    assert len(song_engines.versions()) != 0, "音声合成エンジンがありません。"

    # キャンセル可能エンジンは使用しない
    cancellable_engine: CancellableEngine | None = None

    # 設定ファイルを読み込み
    setting_file = Path(os.getenv("VV_SETTING_FILE", str(USER_SETTING_PATH)))
    setting_loader = SettingHandler(setting_file)
    settings = setting_loader.load()

    # CORS 設定
    cors_policy_mode_str = os.getenv("VV_CORS_POLICY_MODE")
    if cors_policy_mode_str:
        cors_policy_mode = CorsPolicyMode(cors_policy_mode_str)
    else:
        cors_policy_mode = settings.cors_policy_mode

    allow_origin_str = os.getenv("VV_ALLOW_ORIGIN")
    if allow_origin_str:
        allow_origin = allow_origin_str.split(" ")
    elif settings.allow_origin:
        allow_origin = settings.allow_origin.split(" ")
    else:
        allow_origin = None

    # プリセットファイル
    preset_path_str = os.getenv("VV_PRESET_FILE")
    if preset_path_str:
        preset_path = Path(preset_path_str)
    else:
        preset_path = get_save_dir() / "presets.yaml"
    preset_manager = PresetManager(preset_path)

    # ユーザー辞書
    user_dict = UserDictionary()

    # エンジンマニフェスト
    engine_manifest = load_manifest(engine_manifest_path())

    # ライブラリマネージャー
    library_manager = LibraryManager(
        get_save_dir(),
        engine_manifest.supported_vvlib_manifest_version,
        engine_manifest.brand_name,
        engine_manifest.name,
        engine_manifest.uuid,
    )

    # キャラクター情報ディレクトリ
    root_dir = engine_root()
    character_info_dir = root_dir / "resources" / "character_info"
    if not character_info_dir.exists():
        character_info_dir = root_dir / "speaker_info"

    # ASGI アプリケーションを生成
    app = generate_app(
        tts_engines,
        song_engines,
        aivm_manager,
        core_manager,
        setting_loader,
        preset_manager,
        user_dict,
        engine_manifest,
        library_manager,
        cancellable_engine,
        character_info_dir,
        cors_policy_mode,
        allow_origin,
        disable_mutable_api=disable_mutable_api,
    )

    # メモリを明示的に解放
    gc.collect()

    logger.info("AivisSpeech Engine application created successfully")
    return app


# Gunicorn などから直接インポートされるアプリケーションインスタンス
app = create_app()

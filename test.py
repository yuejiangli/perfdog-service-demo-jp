# coding: utf-8

# =============================================================================
# PerfDog automation entry script (NIKKE example)
# PerfDog 自動化エントリースクリプト（NIKKE サンプル）
#
# Workflow / 処理フロー:
#   1. Create the PerfDogService gRPC proxy.
#      PerfDogService の gRPC プロキシを生成する。
#   2. Resolve a USB-connected device by its serial id.
#      シリアル ID で USB 接続中のデバイスを取得する。
#   3. Configure performance metrics & screenshot interval.
#      取得する性能指標とスクリーンショット間隔を設定する。
#   4. Start collection -> sleep / label / note -> stop.
#      計測開始 → 待機 / ラベル / メモ → 計測停止。
#   5. Upload data to PerfDog cloud and export an Excel file locally.
#      データを PerfDog クラウドへアップロードし、ローカルに Excel 出力する。
# =============================================================================

import logging
import os
import threading
import time

import perfdog_pb2
from perfdog import Test, TestAppBuilder
from test_base import create_service, get_all_types, set_floating_window


# Local Excel export directory (sibling "reports/" of this script).
# ローカル Excel 出力先ディレクトリ（本スクリプトと同階層の "reports/"）。
REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')

# -----------------------------------------------------------------------------
# Test target settings -- update for your own device & app.
# 計測対象の設定 -- 実機と対象アプリに合わせて書き換えてください。
#
# DEVICE_SERIAL:
#   USB device serial id. Run `python cmds.py getdevices` to list ids.
#   For Wi-Fi (adb connect) devices, switch to service.get_wifi_device() below.
#   USB デバイスのシリアル ID。`python cmds.py getdevices` で確認可能。
#   "adb connect" 接続の端末を使う場合は service.get_wifi_device() に切り替える。
#
# PACKAGE_NAME:
#   Android package name (or iOS bundle id) of the app under test.
#   計測対象アプリの Android パッケージ名（または iOS バンドル ID）。
#
# CASE_PREFIX:
#   Prefix for the auto-generated case name (e.g. "nikke" -> "nikke_20260519_140000").
#   自動生成されるケース名の接頭辞（例: "nikke" -> "nikke_20260519_140000"）。
#
# Each value also accepts an environment variable override, so CI / shell users
# can run e.g. `PERFDOG_DEVICE=XXXX PERFDOG_PACKAGE=com.example python test.py`.
# 各値は環境変数による上書きにも対応。CI やシェルから
# `PERFDOG_DEVICE=XXXX PERFDOG_PACKAGE=com.example python test.py` のように指定可能。
# -----------------------------------------------------------------------------
DEVICE_SERIAL = os.environ.get('PERFDOG_DEVICE', '2A091FDH300CYB')
PACKAGE_NAME = os.environ.get('PERFDOG_PACKAGE', 'com.proximabeta.nikke')
CASE_PREFIX = os.environ.get('PERFDOG_CASE_PREFIX', 'nikke')


def main():
    # Configure root logger format and level.
    # ルートロガーのフォーマットとレベルを設定する。
    logging.basicConfig(format="%(asctime)s-%(levelname)s: %(message)s", level=logging.INFO)

    # Create the PerfDogService proxy. It internally launches the native
    # PerfDogService binary (path defined in config.py) and connects via gRPC.
    # PerfDogService プロキシを生成する。内部で config.py に定義された
    # ネイティブ PerfDogService バイナリを起動し、gRPC で接続する。
    service = create_service()

    # Floating-window helper APK control (Android only).
    # Disable installation to avoid interrupting automation runs.
    # フローティングウィンドウ補助 APK の制御（Android のみ）。
    # 自動化中の中断を避けるためインストールを無効化する。
    # service.enable_install_apk()   # enable / 有効化
    service.disable_install_apk()    # disable / 無効化（推奨）

    # Resolve the USB device by serial id.
    # Use cmds.py "getdevices" to list available device ids.
    # For "adb connect" devices, use service.get_wifi_device() instead.
    # シリアル ID で USB デバイスを取得する。
    # 利用可能な ID は cmds.py の "getdevices" で確認できる。
    # "adb connect" 経由の端末は service.get_wifi_device() を使うこと。
    device = service.get_usb_device(DEVICE_SERIAL)
    if device is None:
        logging.error("device not found: %s", DEVICE_SERIAL)
        return

    # Run the test against the target package.
    # All metrics below have been verified by `cmds.py gettypes <id>` on this device.
    # 対象パッケージに対して計測を実行する。
    # 下記の指標はすべて `cmds.py gettypes <id>` で本機の対応を確認済み。
    run_test_app(device,
                 package_name=PACKAGE_NAME,
                 types=[
                     perfdog_pb2.FPS,                    # Frames per second / FPS
                     perfdog_pb2.FRAME_TIME,             # Frame time (ms) / フレーム時間
                     perfdog_pb2.CPU_USAGE,              # Process CPU usage / プロセス CPU 使用率
                     perfdog_pb2.NORMALIZED_CPU_USAGE,   # Normalized CPU / 正規化 CPU
                     perfdog_pb2.CORE_USAGE,             # Per-core usage / コア別使用率
                     perfdog_pb2.CORE_FREQUENCY,         # Per-core frequency / コア別周波数
                     perfdog_pb2.CPU_THROTTLING,         # Thermal throttling / サーマルスロットリング
                     perfdog_pb2.THERMAL_STATUS,         # Device thermal state / 端末温度状態
                     perfdog_pb2.MEMORY,                 # Memory (PSS etc.) / メモリ（PSS など）
                     perfdog_pb2.ANDROID_MEMORY_DETAIL,  # Android memory detail / Android メモリ詳細
                     perfdog_pb2.NETWORK_USAGE,          # Network bandwidth / ネットワーク帯域
                     perfdog_pb2.SCREEN_BRIGHTNESS,      # Screen brightness / 画面輝度
                 ],
                 dynamic_types=[
                     # Mali GPU dynamic counters (vendor-specific).
                     # Mali GPU 動的カウンター（ベンダー依存）。
                     (perfdog_pb2.GPU_COUNTER, 'Mali GPU Usage'),
                     (perfdog_pb2.GPU_COUNTER, 'Mali GPU Utilization'),
                     (perfdog_pb2.GPU_COUNTER, 'Mali Memory Bandwidth'),
                     (perfdog_pb2.GPU_COUNTER, 'Mali Overdraw'),
                 ],
                 )


def run_test_app(device, package_name, types=None, dynamic_types=None, enable_all_types=False):
    # Create the Test object that owns the lifecycle of one collection session.
    # 1 回の計測セッションのライフサイクルを管理する Test オブジェクトを生成する。
    test = Test(device)

    # Optional: override memory sampling frequency (seconds, Android only).
    # オプション: メモリ指標のサンプリング周期を上書きする（秒、Android のみ）。
    # device.set_memory_sampling_frequency(4)

    # An Event that is set on the first received perf data sample,
    # used below to block until collection has actually started.
    # 最初の性能データを受信した時にセットされる Event。
    # 後段の wait() で計測の開始確定までブロックするために使う。
    evt = threading.Event()
    test.set_first_perf_data_callback(lambda: evt.set())

    # Streamed per-second perf data callback. Useful while debugging.
    # 1 秒ごとに流れる性能データのコールバック。デバッグ時に有用。
    test.set_perf_data_callback(lambda perf_data: logging.info(perf_data))

    # Error / warning callbacks. Keep them on so problems are visible in logs.
    # エラー / 警告コールバック。問題発生時にログから追えるよう常時有効化する。
    test.set_error_perf_data_callback(lambda perf_data: logging.info("PerfDog: %s", perf_data.errorData.msg))
    test.set_warning_perf_data_callback(lambda perf_data: logging.warning("PerfDog: %s", perf_data.warningData.msg))

    # Hide the on-device floating window (Android automation friendly).
    # 端末上のフローティングウィンドウを非表示にする（Android 自動化向け）。
    set_floating_window(device)

    # Capture a device screenshot every 2 seconds.
    # Screenshots are uploaded with the task and viewable on the PerfDog web console.
    # 2 秒ごとに端末スクリーンショットを取得する。
    # スクリーンショットはタスクと共にアップロードされ、PerfDog Web コンソールで閲覧できる。
    device.set_screenshot_interval(2)

    # Build and bind the test target (the app under test).
    # 計測対象アプリを生成して Test に紐付ける。
    builder = test.create_test_target_builder(TestAppBuilder)
    builder.set_package_name(package_name)
    test.set_test_target(builder.build())

    # If enable_all_types is True, query device-supported metrics and enable them all.
    # Otherwise honor the explicit `types` / `dynamic_types` lists from the caller.
    # enable_all_types が True の場合は対応指標をすべて有効化する。
    # それ以外は呼び出し側から渡された types / dynamic_types のみを有効化する。
    if enable_all_types:
        types, dynamic_types = get_all_types(device)

    if types is not None:
        test.set_types(*types)

    if dynamic_types is not None:
        test.set_dynamic_types(*dynamic_types)

    # APP_STARTUP_TIME forces the app to restart on every run -> disable by default.
    # APP_STARTUP_TIME を有効にすると毎回アプリが再起動される -> 既定では無効化。
    test.disable_type(perfdog_pb2.APP_STARTUP_TIME)

    # SYSTEM_LOG produces a huge volume of system logs -> disable by default.
    # SYSTEM_LOG は大量のシステムログを生成する -> 既定では無効化。
    test.disable_type(perfdog_pb2.SYSTEM_LOG)

    try:
        # Begin performance data collection.
        # 性能データの収集を開始する。
        test.start()

        # Block until the first sample arrives -> guarantees collection is alive.
        # 最初のサンプルが到着するまでブロックし、計測が確実に動いていることを保証する。
        evt.wait()

        # ----- Automation timeline / 自動化シナリオのタイムライン -----
        # The following segment is a placeholder. Replace with your real
        # gameplay / UI automation steps (e.g. via uiautomator2, WDA, etc.).
        # 以下はサンプル区間。実際の操作（uiautomator2、WDA など）に置き換える。

        # Phase 0: warm-up, 30s
        # フェーズ 0: ウォームアップ、30 秒
        time.sleep(30)

        # Mark phase 1 on the timeline.
        # タイムラインにフェーズ 1 のラベルを付ける。
        test.set_label('フェーズ1')

        # Phase 1: 15s
        # フェーズ 1: 15 秒
        time.sleep(15)

        # Attach a free-form note at the current timestamp (ms).
        # 現在のタイムスタンプ（ミリ秒）に自由記述メモを添付する。
        test.add_note('メモ1', int(time.time() * 1000))

        # Phase 2: 15s
        # フェーズ 2: 15 秒
        time.sleep(15)

        # Stop collection. Required before save_data().
        # 計測を停止する。save_data() 呼び出し前に必須。
        test.stop()

        # Persist results: upload to PerfDog cloud + export Excel locally.
        # 結果を保存する: PerfDog クラウドへアップロード + ローカル Excel 出力。
        os.makedirs(REPORT_DIR, exist_ok=True)
        case_name = '{}_{}'.format(CASE_PREFIX, time.strftime('%Y%m%d_%H%M%S'))
        test.save_data(
            case_name=case_name,
            is_upload=True,                                  # upload to cloud / クラウド送信
            is_export=True,                                  # also export locally / ローカル出力も行う
            export_format=perfdog_pb2.EXPORT_TO_EXCEL,       # xlsx format / xlsx 形式
            export_directory=REPORT_DIR,                     # output dir / 出力ディレクトリ
        )
        logging.info('Excel exported to: %s (case: %s)', REPORT_DIR, case_name)

    finally:
        # Safety net: ensure collection is stopped even if an exception was raised.
        # 安全策: 例外発生時でも計測が停止されるようにする。
        if test.is_start():
            test.stop()


if __name__ == '__main__':
    main()

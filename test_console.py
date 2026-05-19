# coding: utf-8

# =============================================================================
# Console (PlayStation 5 / Xbox) performance collection sample.
# コンシューマ機（PlayStation 5 / Xbox）向け性能計測サンプル。
# =============================================================================

import logging
import threading
import time

import perfdog_pb2
from perfdog import Test, TestSysProcessBuilder, TestAppBuilder
from test_base import create_service, get_all_types


def main():
    # Configure root logger format and level.
    # ルートロガーのフォーマットとレベルを設定する。
    logging.basicConfig(format="%(asctime)s-%(levelname)s: %(message)s", level=logging.INFO)

    # Create the PerfDogService gRPC proxy.
    # PerfDogService の gRPC プロキシを生成する。
    service = create_service()

    # TODO:
    # Register console devices. Usually only required the first time.
    # コンシューマ機を登録する。通常は初回のみ必要。
    service.add_remote_play_station_device(ip_address="192.168.0.0")
    service.add_remote_xbox_device(ip_address="192.168.0.0", password="test")
    time.sleep(2)

    # TODO:
    # Resolve a Wi-Fi device by its serial id.
    # Use cmds.py "getdevices" to list available device ids.
    # シリアル ID で Wi-Fi 端末を解決する。
    # 利用可能な ID は cmds.py の "getdevices" で確認できる。
    device = service.get_wifi_device('-')
    if device is None:
        logging.error("non-exist device")
        return

    # Check whether the device is already occupied by another user.
    # 当端末が他ユーザーに占有されていないか確認する。
    other_user = device.occupied_by_other_user()
    if other_user:
        logging.info("device occupied by %s", other_user)

    # TODO:
    # Continuing past this point will forcibly take over the device.
    # Fill in the package name of the app under test.
    # この先に進むと端末を強制的に奪取する。
    # 計測対象アプリのパッケージ名を入力すること。
    run_test(device=device, package_name='-', types=[perfdog_pb2.FPS, perfdog_pb2.FRAME_TIME])


def run_test(device, package_name, types=None, dynamic_types=None, enable_all_types=False):
    # Create the Test object that owns the lifecycle of one collection session.
    # 1 回の計測セッションのライフサイクルを管理する Test オブジェクトを生成する。
    test = Test(device)

    # Event flag fired on the first received perf-data sample.
    # 最初の性能データを受信した時にセットされる Event フラグ。
    evt = threading.Event()
    test.set_first_perf_data_callback(lambda: evt.set())

    # Per-second perf-data callback. Useful while debugging.
    # 1 秒ごとに流れる性能データのコールバック。デバッグ時に有用。
    test.set_perf_data_callback(lambda perf_data: logging.info(perf_data))

    # Error / warning callbacks. Keep them on so problems are visible in logs.
    # エラー / 警告コールバック。問題発生時にログから追えるよう常時有効化する。
    test.set_error_perf_data_callback(lambda perf_data: logging.info("PerfDog: %s", perf_data.errorData.msg))
    test.set_warning_perf_data_callback(lambda perf_data: logging.warning("PerfDog: %s", perf_data.warningData.msg))

    # Build the test target. PS5 also supports targeting a system process.
    # 計測対象を生成する。PS5 はシステムプロセスを対象にすることも可能。
    builder = test.create_test_target_builder(TestAppBuilder)
    builder.set_package_name(package_name)
    # builder = test.create_test_target_builder(TestSysProcessBuilder)
    # builder.set_pid(pid)
    test.set_test_target(builder.build())

    # Enable / disable performance metric types.
    # 関連する性能指標を有効化 / 無効化する。
    if enable_all_types:
        types, dynamic_types = get_all_types(device)

    if types is not None:
        test.set_types(*types)

    if dynamic_types is not None:
        test.set_dynamic_types(*dynamic_types)

    try:
        # Begin performance data collection.
        # 性能データの収集を開始する。
        test.start()

        # Block until the first sample arrives.
        # Requires set_first_perf_data_callback() above.
        # 最初のサンプルが届くまでブロックする。
        # 上の set_first_perf_data_callback() が必須。
        evt.wait()

        # TODO:
        # Insert your real automation steps here.
        # 実際の自動化操作はここに追加する。
        time.sleep(10)
        test.set_label('label_x')
        time.sleep(2)
        test.add_note('n1', 12 * 1000)
        time.sleep(2)
        test.stop()
        test.save_data()

    finally:
        # Safety net: ensure collection is stopped even if an exception was raised.
        # 安全策: 例外発生時でも計測が確実に停止されるようにする。
        if test.is_start():
            test.stop()


if __name__ == '__main__':
    main()

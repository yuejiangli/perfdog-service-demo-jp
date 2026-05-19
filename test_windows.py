# coding: utf-8

# =============================================================================
# Windows performance collection sample.
# Must be launched from a terminal started "as Administrator".
#
# Windows 向け性能計測サンプル。
# 「管理者として実行」したターミナルから起動すること。
# =============================================================================

import logging
import threading
import time

import perfdog_pb2
from perfdog import Test, TestSysProcessBuilder
from test_base import create_service, get_all_types, set_floating_window


def get_windows_device(service):
    # Pick the first Windows device discovered by the service.
    # Service が認識した Windows 端末のうち最初の 1 台を返す。
    for device in service.get_devices():
        if device.os_type() == perfdog_pb2.WINDOWS:
            return device
    return None


def main():
    # Configure root logger format and level.
    # ルートロガーのフォーマットとレベルを設定する。
    logging.basicConfig(format="%(asctime)s-%(levelname)s: %(message)s", level=logging.INFO)

    # Create the PerfDogService gRPC proxy.
    # PerfDogService の gRPC プロキシを生成する。
    service = create_service()

    # Resolve the local Windows device.
    # ローカルの Windows 端末を解決する。
    device = get_windows_device(service)
    if device is None:
        logging.error("non-exist device")
        return

    # TODO:
    # Fill in the correct process PID and the DirectX version used by the
    # target process for rendering. The metric list below is also editable;
    # passing types=None reuses metrics already enabled on this device.
    # 計測対象プロセスの PID と、レンダリングに用いる DirectX バージョンを入力する。
    # 性能指標リストも編集可能。types=None を渡すと、当端末で既に有効化されて
    # いる指標がそのまま使われる。
    # Metric reference: https://perfdog.qq.com/article_detail?id=10210&issue_id=0&plat_id=2
    # 指標リファレンス: https://perfdog.qq.com/article_detail?id=10210&issue_id=0&plat_id=2
    pid = 30120
    dx_version = perfdog_pb2.AUTO
    run_test(device, pid=pid, dx_version=dx_version,
             types=[perfdog_pb2.FPS, perfdog_pb2.FRAME_TIME, perfdog_pb2.WINDOWS_CPU, perfdog_pb2.WINDOWS_MEMORY],
             )


def run_test(device, pid, dx_version, types=None, dynamic_types=None, enable_all_types=False):
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

    # Hide the on-device floating overlay (recommended for automation).
    # 端末上のフローティング表示を非表示にする（自動化実行時に推奨）。
    set_floating_window(device)

    # Build the test target (system process under test).
    # 計測対象（システムプロセス）を生成する。
    builder = test.create_test_target_builder(TestSysProcessBuilder)
    builder.set_pid(pid)
    builder.set_dx_version(dx_version)
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

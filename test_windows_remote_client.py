# coding: utf-8

# =============================================================================
# Remote-Windows client sample.
# Continuously refreshes the remote Windows device list and prints status.
# Run me on the operator's PC; the remote PC must be running PerfDogService
# in "remote collector" mode (see test_windows_remote_server.py).
#
# Windows リモート計測 クライアント側サンプル。
# リモート Windows 端末の一覧を継続的に更新し、状態を出力する。
# 操作者側 PC で実行する。リモート PC 側では「リモート コレクタ」モードで
# PerfDogService を起動しておくこと（test_windows_remote_server.py 参照）。
# =============================================================================

import logging
import time

import perfdog_pb2
from test_base import create_service


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

    # Periodically refresh the remote-Windows device list and resolve a target.
    # リモート Windows 端末の一覧を定期的に更新し、対象を解決する。
    while True:
        # Refresh the remote computer list.
        # リモート PC の一覧を更新する。
        service.update_remote_windows_device()

        # Get a remote Windows device object.
        # リモート Windows 端末オブジェクトを取得する。
        device = get_windows_device(service)
        if device is None:
            logging.error("non-exist device")
            return
        time.sleep(2)


if __name__ == '__main__':
    main()

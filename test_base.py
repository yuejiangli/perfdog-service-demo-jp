# coding: utf-8

# =============================================================================
# Shared helpers used by every test_*.py entry script.
#   - create_service()       : build a Service proxy bound to the local port.
#   - get_all_types()        : return every metric supported by the device.
#   - set_floating_window()  : hide the on-device floating overlay.
#
# 各 test_*.py から共通利用するヘルパー群。
#   - create_service()       : ローカルポートに紐付く Service プロキシを生成。
#   - get_all_types()        : 端末がサポートする全指標を返却。
#   - set_floating_window()  : 端末上のフローティング表示を非表示にする。
# =============================================================================

import logging
import perfdog_pb2

from config import SERVICE_TOKEN, SERVICE_PATH
from perfdog import Service


def create_service(port=23456):
    # Build the Service proxy. Internally launches the native PerfDogService
    # binary (path defined in config.py) and connects via gRPC on `port`.
    # Service プロキシを生成する。内部で config.py に定義された
    # PerfDogService バイナリを起動し、`port` 経由 gRPC で接続する。
    service = Service(SERVICE_TOKEN, SERVICE_PATH, port=port)

    # Subscribe to device add/remove events so connect/disconnect is logged.
    # 端末の接続 / 切断イベントを購読し、ログに残す。
    service.get_device_event_stream(lambda event: print_device(event))
    return service


def get_all_types(device):
    # Return (static_types, dynamic_types) supported by the device.
    # 当端末でサポートされる (静的指標, 動的指標) を返す。
    types, dynamicTypes = device.get_available_types()
    return [ty for ty in types], [(dynamicType.type, dynamicType.category) for dynamicType in dynamicTypes]


def set_floating_window(device):
    # Hide the floating overlay on the device side. Recommended for automation.
    # 端末上のフローティング表示を隠す。自動化実行時に推奨。
    position = perfdog_pb2.HIDE
    font_color = perfdog_pb2.Color(red=0.49, green=0.93, blue=0.89, alpha=1.0)
    record_hotkey = ''
    add_label_hotkey = ''
    device.set_floating_window_preferences(position, font_color, record_hotkey, add_label_hotkey)


def print_device(event):
    # Log a one-line message for each device add/remove event.
    # 端末の追加 / 削除イベントを 1 行のログとして出力する。
    if event.eventType == perfdog_pb2.ADD:
        logging.info("AddDevice: \n%s", event.device)
    elif event.eventType == perfdog_pb2.REMOVE:
        logging.info("RemoveDevice: \n%s", event.device)

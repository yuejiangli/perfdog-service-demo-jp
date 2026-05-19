# coding: utf-8

# =============================================================================
# Reference snippets that demonstrate seldom-used Service / Device APIs.
# This file is meant for reading, not for running directly.
#
# あまり使われない Service / Device 系 API の参考スニペット集。
# 直接実行するためではなく、読むためのファイル。
# =============================================================================

import logging
import time
from perfdog import Service, Test, TestSysProcessBuilder
import perfdog_pb2


def run(service, device_id=None,
        upload_url=None,
        case_id=None,
        task_name=None,
        package_name=None):
    # Iterate every device known to the service.
    # Service が認識している端末を列挙する。
    for device in service.get_devices():
        logging.info(device)

    # Subscribe to device add / remove events.
    # 端末の追加 / 削除イベントを購読する。
    # stream = service.get_device_event_stream(lambda e: logging.info(e))
    # time.sleep(30)
    # stream.stop()

    # Configure a third-party data upload server (per-process global setting).
    # 第三者データアップロード先を設定する（プロセスグローバル設定）。
    if upload_url is not None:
        service.set_global_data_upload_server(upload_url, perfdog_pb2.JSON)
        service.clear_global_data_upload_server()

    # Share a case. Expiration is in minutes.
    # ケースを共有する。有効期限は「分」単位。
    if case_id is not None:
        logging.info("shareCase: %s", service.share_case(case_id, 8 * 24 * 60))

    # Create a task and archive an existing case into it.
    # タスクを作成し、既存ケースをアーカイブする。
    if task_name is not None and case_id is not None:
        task_id = service.create_task(task_name)
        service.archive_case_to_task(task_id, case_id)

    # API smoke test against a single device.
    # 単一端末に対する API の疎通確認。
    device = service.get_usb_device(device_id)
    if device is not None:
        # Initialize the device.
        # 端末を初期化する。
        device.init()

        # Fetch device info.
        # 端末情報を取得する。
        logging.info('get_info: %s', device.get_info())

        # Fetch current device status.
        # 端末の現在ステータスを取得する。
        logging.info('get_status: %s', device.get_status())

        # List installed apps.
        # インストール済みアプリ一覧を取得する。
        apps = device.get_apps()
        for app in apps:
            logging.info(app.packageName)

        # Look up an app by package name.
        # パッケージ名でアプリを検索する。
        app = device.get_app(package_name)
        logging.info('get_app: %s', app)
        # logging.info('get_app_running_processes: %s', device.get_app_running_processes(app))
        # logging.info('get_app_windows_map: %s', device.get_app_windows_map(app))
        # logging.info('get_sys_processes: %s', device.get_sys_processes())

        # Set screenshot interval (in seconds; uploaded together with the task).
        # スクリーンショット間隔を設定する（秒単位、タスクと共にアップロード）。
        # device.set_screenshot_interval(6)

    # Stop PerfDogService.
    # PerfDogService を停止する。
    # service.kill_server()

    return


def run_test_sys_process(device, process_name):
    # Minimal example: collect for 30s against a system process.
    # 最小例: システムプロセスを対象に 30 秒間収集する。
    test = Test(device)
    builder = test.create_test_target_builder(TestSysProcessBuilder)
    builder.set_process_name(process_name)
    test.set_test_target(builder.build())
    test.start()
    time.sleep(30)
    test.stop()
    test.save_data()

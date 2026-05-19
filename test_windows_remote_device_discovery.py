# coding: utf-8

# =============================================================================
# Remote-Windows device discovery utility.
# Lists every Windows device currently visible through PerfDogService and lets
# the user generate ready-to-paste device-config snippets.
#
# Windows リモート端末ディスカバリツール。
# PerfDogService から見える Windows 端末を一覧表示し、そのままコピー利用できる
# デバイス設定スニペットを生成する。
# =============================================================================

import logging
import sys
import time
import perfdog_pb2
from test_base import create_service


def discover_devices(port=23456):
    """Discover and display all available devices.
    全ての利用可能な端末を検出して表示する。
    """

    logging.basicConfig(
        format="%(asctime)s-%(levelname)s: %(message)s",
        level=logging.INFO
    )

    print("=== PerfDog device discovery / 端末ディスカバリ ===")
    print()

    # Create the Service proxy.
    # Service プロキシを生成する。
    try:
        service = create_service(port=port)
        logging.info(f"Service connected successfully on port {port}")
    except Exception as e:
        logging.error(f"Failed to connect to PerfDog service on port {port}: {e}")
        return []

    # Refresh remote Windows device list.
    # リモート Windows 端末一覧を更新する。
    try:
        logging.info("Refreshing remote device list...")
        service.update_remote_windows_device()
        # Wait for the device list to be updated.
        # デバイス一覧の更新を待機する。
        time.sleep(2)
    except Exception as e:
        logging.warning(f"Failed to refresh remote devices: {e}")

    # Fetch every device.
    # 全端末を取得する。
    try:
        all_devices = service.get_devices()
        logging.info(f"Found {len(all_devices)} total devices")
    except Exception as e:
        logging.error(f"Failed to get device list: {e}")
        return []

    # Filter Windows devices.
    # Windows 端末のみ抽出する。
    windows_devices = []
    for device in all_devices:
        if device.os_type() == perfdog_pb2.WINDOWS:
            windows_devices.append(device)

    if not windows_devices:
        logging.warning("No Windows devices found")
        return []

    logging.info(f"Found {len(windows_devices)} Windows devices:")
    print()
    print("=" * 100)
    print(f"{'#':<3} {'Device Name':<30} {'Device ID':<40} {'Access Type':<15} {'Connection':<10}")
    print("=" * 100)

    device_info_list = []

    for i, device in enumerate(windows_devices):
        try:
            real_dev = device.real_device()
            access_type_info = "Unknown"
            access_type_raw = None

            # Read the access type field if available.
            # アクセスタイプフィールドが存在すれば読み出す。
            if hasattr(real_dev, 'accessType'):
                access_type_raw = real_dev.accessType
            elif hasattr(real_dev, 'access_type'):
                access_type_raw = real_dev.access_type

            # Convert to a human-readable string.
            # 人間が読める文字列に変換する。
            if access_type_raw is not None:
                if access_type_raw == perfdog_pb2.LOCAL:
                    # If the device name contains "(Remote)" but access_type is
                    # LOCAL, this entry is the local proxy of a remote device.
                    # 端末名に "(Remote)" を含むが access_type が LOCAL の場合、
                    # それはリモート端末のローカルプロキシ。
                    if "(Remote)" in device.name():
                        access_type_info = "REMOTE_LOCAL"
                    else:
                        access_type_info = "LOCAL"
                elif access_type_raw == perfdog_pb2.REMOTE_REACHABLE:
                    access_type_info = "REMOTE_REACHABLE"
                elif access_type_raw == perfdog_pb2.REMOTE_UNREACHABLE:
                    access_type_info = "REMOTE_UNREACHABLE"
                else:
                    access_type_info = f"Unknown({access_type_raw})"
            else:
                if "(Remote)" in device.name():
                    access_type_info = "REMOTE(by_name)"
                else:
                    conn_type = device.conn_type()
                    if conn_type == perfdog_pb2.USB:
                        access_type_info = "LOCAL(USB)"
                    elif conn_type == perfdog_pb2.WIFI:
                        access_type_info = "REMOTE(WIFI)"

            # Connection type. For remote devices we report NETWORK explicitly.
            # 接続タイプ。リモート端末は NETWORK と明示的に表示する。
            conn_type = device.conn_type()
            if "(Remote)" in device.name():
                # Remote devices reach the local PerfDogService over the network.
                # リモート端末はネットワーク経由でローカル PerfDogService に接続する。
                conn_type_str = "NETWORK"
            else:
                conn_type_str = "USB" if conn_type == perfdog_pb2.USB else "WIFI"

            device_info = {
                'index': i + 1,
                'name': device.name(),
                'uid': device.uid(),
                'access_type': access_type_info,
                'conn_type': conn_type_str,
                'device_obj': device
            }

            device_info_list.append(device_info)

            print(f"{i+1:<3} {device.name():<30} {device.uid():<40} {access_type_info:<15} {conn_type_str:<10}")

        except Exception as e:
            logging.warning(f"Failed to get info for device {i+1}: {e}")

    print("=" * 100)
    print()

    return device_info_list


def interactive_mode():
    """Interactive mode.
    対話モード。
    """

    # Run discovery first.
    # まず端末ディスカバリを実行する。
    devices = discover_devices()
    if not devices:
        return

    while True:
        print("\n=== Menu / メニュー ===")
        print("1. Generate device config snippet / 端末設定スニペットを生成")
        print("2. Rescan devices / 端末を再スキャン")
        print("3. Quit / 終了")

        choice = input("\nSelect (1-3) / 選択 (1-3): ").strip()

        if choice == '1':
            # Generate config code.
            # 設定コードを生成する。
            print("\n=== Generate device config / 端末設定の生成 ===")
            selected_devices = input(
                "Enter device numbers (comma separated, e.g. 1,2,3) / "
                "端末番号をカンマ区切りで入力（例: 1,2,3）: "
            ).strip()

            try:
                device_indices = [int(x.strip()) - 1 for x in selected_devices.split(',')]
                generate_config_code(devices, device_indices)
            except ValueError:
                print("Invalid device number / 無効な端末番号です")

        elif choice == '2':
            # Rescan devices.
            # 端末を再スキャンする。
            devices = discover_devices()
            if not devices:
                break

        elif choice == '3':
            print("Bye / 終了します")
            break

        else:
            print("Invalid selection, try again / 無効な選択です。再入力してください。")


def generate_config_code(devices, device_indices):
    """Generate device configuration code.
    端末設定コードを生成する。
    """

    print("\n=== Generated device config / 生成された端末設定 ===")
    print()

    for i, index in enumerate(device_indices):
        if 0 <= index < len(devices):
            device_info = devices[index]

            # Ask the user which PID to test on this device.
            # この端末で計測する対象プロセスの PID をユーザーに尋ねる。
            pid_input = input(
                f"PID for device '{device_info['name']}' / "
                f"端末 '{device_info['name']}' で計測する PID: "
            ).strip()
            try:
                pid = int(pid_input)
            except ValueError:
                # Default value when no PID is provided.
                # PID 未入力時の既定値。
                pid = 1234
                print(f"Using default PID / 既定 PID を使用: {pid}")

            print(f"        {{")
            print(f"            'device_id': '{device_info['uid']}',")
            print(f"            'pid': {pid},")
            print(f"            'test_duration': 60,")
            print(f"            'cycle_interval': 15,")
            print(f"            'max_cycles': 3")
            print(f"        }},")

            if i < len(device_indices) - 1:
                print()

    print("\n=== Config generation done / 設定生成完了 ===")


def main():
    """Entry point.
    エントリポイント。
    """

    if len(sys.argv) > 1:
        if sys.argv[1] == '--list':
            # List devices only.
            # 端末一覧のみ表示する。
            discover_devices()
        elif sys.argv[1] == '--port' and len(sys.argv) > 2:
            # Use a custom port.
            # 任意のポートを指定する。
            try:
                port = int(sys.argv[2])
                discover_devices(port)
            except ValueError:
                print("Invalid port number")
        else:
            print("Usage: python test_windows_remote_device_discovery.py [--list] [--port PORT_NUMBER]")
    else:
        # Interactive mode.
        # 対話モード。
        interactive_mode()


if __name__ == '__main__':
    main()

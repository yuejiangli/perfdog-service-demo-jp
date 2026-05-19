# coding: utf-8

# =============================================================================
# CLI helper: query devices / apps / processes / metrics, and stop the service.
# CLI ヘルパー: 端末 / アプリ / プロセス / 指標一覧の取得、Service の停止。
#
# Usage / 使い方:
#   python cmds.py getdevices
#   python cmds.py getapps <device_id>
#   python cmds.py getsysprocesses <device_id>
#   python cmds.py gettypes <device_id>
#   python cmds.py getpresetnetworktemplate
#   python cmds.py killserver
# =============================================================================

import sys

import perfdog_pb2
from config import SERVICE_TOKEN, SERVICE_PATH
from perfdog import Service


def print_devices(service):
    # List all devices currently visible to PerfDogService.
    # PerfDogService が認識している全端末を一覧表示する。
    for device in service.get_devices():
        print(device)


def print_apps(service, device_id):
    # Resolve the device by id (USB first, then Wi-Fi).
    # 端末 ID から端末を解決する（USB を優先、なければ Wi-Fi）。
    device = service.get_usb_device(device_id)
    if device is None:
        device = service.get_wifi_device(device_id)
        if device is None:
            print('device not found')
            return

    # Initialize the device if it has not been initialized yet.
    # 端末が未初期化の場合は初期化を行う。
    status = device.get_status()
    if not status.isValid:
        device.init()

    # Print every installed app's package name and human-readable label.
    # インストール済みアプリのパッケージ名と表示名を出力する。
    for app in device.get_apps():
        print(app.packageName, app.label)


def print_sys_processes(service, device_id):
    # Resolve the device by id (USB first, then Wi-Fi).
    # 端末 ID から端末を解決する（USB を優先、なければ Wi-Fi）。
    device = service.get_usb_device(device_id)
    if device is None:
        device = service.get_wifi_device(device_id)
        if device is None:
            return

    status = device.get_status()
    if not status.isValid:
        device.init()

    # Print "<pid> <name>" for every running system process.
    # 実行中のシステムプロセスを「<pid> <name>」形式で出力する。
    for process in device.get_sys_processes():
        print(process.pid, process.name)


def print_types(service, device_id):
    # Resolve the device by id (USB first, then Wi-Fi).
    # 端末 ID から端末を解決する（USB を優先、なければ Wi-Fi）。
    device = service.get_usb_device(device_id)
    if device is None:
        device = service.get_wifi_device(device_id)
        if device is None:
            return

    status = device.get_status()
    if not status.isValid:
        device.init()

    # Print supported static metrics and dynamic metrics for this device.
    # 当端末がサポートする静的指標と動的指標を一覧表示する。
    types, dynamicTypes = device.get_available_types()
    for index, ty in enumerate(types):
        try:
            print('type[{}]: perfdog_pb2.{}'.format(index, perfdog_pb2.PerfDataType.Name(ty)))
        except ValueError:
            pass

    for index, dynamicType in enumerate(dynamicTypes):
        try:
            print('dynamicType[{}]: perfdog_pb2.{}, {}'.format(
                index,
                perfdog_pb2.DynamicPerfDataType.Name(dynamicType.type),
                dynamicType.category))
        except ValueError:
            pass


def print_preset_network_template(service):
    # Print preset + saved user-defined network templates.
    # プリセットおよびユーザー保存済みのネットワークテンプレートを出力する。
    templates = service.get_preset_network_template()
    for template in templates:
        print('id:{},name:{},description:{}'.format(template.id, template.name, template.description))


def kill_server(service):
    # Stop PerfDogService gracefully (important to avoid background billing).
    # PerfDogService を正しく停止する（バックグラウンド課金を避けるため必須）。
    service.kill_server()


def print_usage():
    print('usage: python cmds.py getdevices')
    print('       python cmds.py getapps device_id')
    print('       python cmds.py getsysprocesses device_id')
    print('       python cmds.py gettypes device_id')
    print('       python cmds.py getpresetnetworktemplate')
    print('       python cmds.py killserver')


def get_func_and_args(args):
    # Map CLI sub-command to the matching python function.
    # CLI サブコマンドを対応する Python 関数にマッピングする。
    if len(args) == 0:
        return None, ()

    cmd = args[0]
    args = args[1:]

    if cmd == 'getdevices' and len(args) == 0:
        return print_devices, args

    if cmd == 'getapps' and len(args) == 1:
        return print_apps, args

    if cmd == 'getsysprocesses' and len(args) == 1:
        return print_sys_processes, args

    if cmd == 'gettypes' and len(args) == 1:
        return print_types, args

    if cmd == 'getpresetnetworktemplate' and len(args) == 0:
        return print_preset_network_template, args

    if cmd == 'killserver' and len(args) == 0:
        return kill_server, args

    return None, ()


def main():
    # Parse CLI args, build the Service proxy, then dispatch.
    # CLI 引数を解析し、Service プロキシを生成して関数を実行する。
    func, args = get_func_and_args(sys.argv[1:])
    if func is None:
        print_usage()
        return

    service = Service(SERVICE_TOKEN, SERVICE_PATH)
    func(service, *args)


if __name__ == '__main__':
    main()

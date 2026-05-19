# coding: utf-8

# =============================================================================
# Network (weak-network simulation) test sample for Windows targets.
# Windows 向け 弱ネットワークシミュレーション計測サンプル。
# =============================================================================

import logging
import time

import perfdog_pb2
from perfdog import Test, TestSysProcessBuilder
from test_base import create_service


def get_windows_device(service):
    # Pick the first Windows device discovered by the service.
    # Service が認識した Windows 端末のうち最初の 1 台を返す。
    for device in service.get_devices():
        if device.os_type() == perfdog_pb2.WINDOWS:
            return device
    return None


def create_customized_template():
    # Build a user-defined network template (uplink + downlink shaping rules).
    # ユーザー定義のネットワークテンプレートを生成する（上下両方向のシェーピング設定）。
    template = perfdog_pb2.NetworkProfilingTemplate()
    template.name = "test"
    template.description = "test"

    option = template.networkProfilingOptions.add()

    # The following fields are all optional; set only what you need.
    # 以下のフィールドはすべて任意。必要なものだけ設定すれば良い。

    # Upstream bandwidth (kbps).
    # 上り帯域（kbps）。
    option.outBandwidth.value = 1000

    # Upstream delay (ms).
    # 上り遅延（ミリ秒）。
    option.outDelay.value = 1000

    # Upstream delay jitter range.
    # 上り遅延ジッタ範囲。
    outDelayBias = option.outDelayBias.add()
    outDelayBias.delayBiasMin = 0
    outDelayBias.delayBiasMax = 1000
    outDelayBias.delayBiasPercent = 50

    # Upstream random packet-loss rate (1-100, integer).
    # 上り方向のランダムパケットロス率（1-100、整数）。
    option.outRate.value = 100

    # Upstream periodic shaping.
    # outPass + outLoss : pass-through window then full-loss window.
    # outPass + outBurst: pass-through window then delayed-release window.
    # 上り方向の周期的シェーピング。
    # outPass + outLoss : 正常通過時間 + 完全ロス時間。
    # outPass + outBurst: 正常通過時間 + 遅延適用時間。
    option.outPass.value = 1000
    option.outLoss.value = 1000
    option.outBurst.value = 1000

    # Downstream bandwidth (kbps).
    # 下り帯域（kbps）。
    option.inBandwidth.value = 1000

    # Downstream delay (ms).
    # 下り遅延（ミリ秒）。
    option.inDelay.value = 1000

    # Downstream delay jitter range.
    # 下り遅延ジッタ範囲。
    inDelayBias = option.inDelayBias.add()
    inDelayBias.delayBiasMin = 0
    inDelayBias.delayBiasMax = 1000
    inDelayBias.delayBiasPercent = 50

    # Downstream random packet-loss rate (1-100, integer).
    # 下り方向のランダムパケットロス率（1-100、整数）。
    option.inRate.value = 100

    # Downstream periodic shaping. Same semantics as upstream.
    # 下り方向の周期的シェーピング。意味は上り方向と同じ。
    option.inPass.value = 1000
    option.inLoss.value = 1000
    option.inBurst.value = 1000

    # Apply weak-network simulation only to these protocols.
    # 弱ネットワーク適用対象プロトコル。
    option.affectedProtocol.append(perfdog_pb2.TCP)
    option.affectedProtocol.append(perfdog_pb2.UDP)
    option.affectedProtocol.append(perfdog_pb2.DNS)
    option.affectedProtocol.append(perfdog_pb2.ICMP)

    # Restrict the weak-network effect to specific destination IPs.
    # 弱ネットワーク適用対象 IP を限定する。
    # option.ipList.append("127.0.0.1")

    return template


# Build a list of network templates for the test run.
# 計測実行時に使用するネットワークテンプレート一覧を生成する。
def create_templates(service):
    # Fetch user templates (preset + user-saved). Preset scene templates are
    # currently unavailable on Windows.
    # ユーザーのネットワークテンプレートを取得する。Windows ではプリセットの
    # シーンテンプレートが現状利用できない点に注意。
    templates = service.get_preset_network_template(perfdog_pb2.WINDOWS)
    for template in templates:
        logging.info("id:%d,name:%s,description:%s", template.id, template.name, template.description)

    # Build an additional user-defined template.
    # 追加でユーザー定義テンプレートを 1 件生成する。
    user_template = create_customized_template()

    # Optionally upload user-defined template to the server.
    # 任意でサーバーへアップロードする。
    # service.submit_user_network_template(user_template)

    # Pick the templates that will actually be used during the test.
    # 実際の計測で使用するテンプレートを選択する。
    test_templates = [templates[1]]
    test_templates.append(user_template)
    return test_templates


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
    # Fill in the correct process PID for the app under test.
    # Use cmds.py "getsysprocesses" to list current Windows processes.
    # 計測対象プロセスの PID を入力する。
    # 現在の Windows プロセス一覧は cmds.py の "getsysprocesses" で確認できる。
    pid = 20740
    run_test(device, pid, create_templates(service))


def run_test(device, pid, templates):
    # Create the Test object that owns the lifecycle of one collection session.
    # 1 回の計測セッションのライフサイクルを管理する Test オブジェクトを生成する。
    test = Test(device)

    # Build the test target (system process under test).
    # 計測対象（システムプロセス）を生成する。
    builder = test.create_test_target_builder(TestSysProcessBuilder)
    builder.set_pid(pid)
    builder.set_profiling_mode(perfdog_pb2.NETWORK)
    builder.set_network_template(templates[0])
    test.set_test_target(builder.build())

    try:
        # Begin performance data collection.
        # 性能データの収集を開始する。
        test.start()

        # Log which network template is in effect at start.
        # 計測開始時に適用中のテンプレートをログ出力する。
        logging.info("start with network template: %s", templates[0].name)

        # TODO:
        # Insert your real automation steps here.
        # The active network template can be switched mid-run.
        # 実際の自動化操作はここに追加する。
        # 計測中にネットワークテンプレートを切り替えることも可能。
        for template in templates[1:]:
            time.sleep(10)
            test.set_label(template.name)
            device.change_network_template(template)
            logging.info("change network template: %s", template.name)

        time.sleep(2)
        test.stop()

    finally:
        # Safety net: ensure collection is stopped even if an exception was raised.
        # 安全策: 例外発生時でも計測が確実に停止されるようにする。
        if test.is_start():
            test.stop()


if __name__ == '__main__':
    main()

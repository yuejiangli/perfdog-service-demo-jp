# coding: utf-8

# =============================================================================
# Network (weak-network simulation) test sample for Android / iOS targets.
# Android / iOS 向け 弱ネットワークシミュレーション計測サンプル。
# =============================================================================

import logging
import time

import perfdog_pb2
from perfdog import Test, TestAppBuilder
from test_base import create_service


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
    # Lower bound of the jitter range (ms).
    # ジッタ範囲の下限（ミリ秒）。
    outDelayBias.delayBiasMin = 0
    # Upper bound of the jitter range (ms).
    # ジッタ範囲の上限（ミリ秒）。
    outDelayBias.delayBiasMax = 1000
    # Probability that jitter is applied (1-100, %).
    # ジッタが適用される確率（1-100、%）。
    outDelayBias.delayBiasPercent = 50

    # Upstream random packet-loss rate (1-100, integer).
    # 上り方向のランダムパケットロス率（1-100、整数）。
    option.outRate.value = 100

    # Upstream periodic shaping.
    # outPass + outLoss : pass-through window then full-loss window.
    # outPass + outBurst: pass-through window then delayed-release window
    #                     (packets buffered during burst-window are released
    #                     when the next pass-through window starts).
    # 上り方向の周期的シェーピング。
    # outPass + outLoss : 正常通過時間 + 完全ロス時間。
    # outPass + outBurst: 正常通過時間 + 遅延適用時間（バースト時間中の
    #                     パケットは次の通過時間が来るまで保留される）。
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
    # Other protocols pass through untouched.
    # 弱ネットワーク適用対象プロトコル。リスト外のプロトコルは素通しになる。
    option.affectedProtocol.append(perfdog_pb2.TCP)
    option.affectedProtocol.append(perfdog_pb2.UDP)
    option.affectedProtocol.append(perfdog_pb2.DNS)
    option.affectedProtocol.append(perfdog_pb2.ICMP)

    # Restrict the weak-network effect to specific destination IPs.
    # If empty, the effect applies to every destination.
    # 弱ネットワークを適用する宛先 IP を限定する。
    # 未指定の場合は全ての宛先に適用される。
    option.ipList.append("127.0.0.1")

    return template


# Build a list of network templates for the test run.
# 計測実行時に使用するネットワークテンプレート一覧を生成する。
def create_templates(service):
    # Fetch user templates (preset + user-saved).
    # ユーザーのネットワークテンプレートを取得する（プリセット + 保存済みカスタム）。
    templates = service.get_preset_network_template()
    for template in templates:
        logging.info("id:%d,name:%s,description:%s", template.id, template.name, template.description)

    # Build an additional user-defined template.
    # 追加でユーザー定義テンプレートを 1 件生成する。
    user_template = create_customized_template()

    # Optionally upload user-defined template to the server, so future calls to
    # get_preset_network_template() can re-fetch it.
    # 任意でサーバーへアップロードする。アップロード後は次回以降の
    # get_preset_network_template() で再取得できる。
    # service.submit_user_network_template(user_template)

    # Pick the templates that will actually be used during the test.
    # 実際の計測で使用するテンプレートを選択する。
    test_templates = templates[:6]
    test_templates.append(user_template)
    return test_templates


def main():
    # Configure root logger format and level.
    # ルートロガーのフォーマットとレベルを設定する。
    logging.basicConfig(format="%(asctime)s-%(levelname)s: %(message)s", level=logging.INFO)

    # Create the PerfDogService gRPC proxy.
    # PerfDogService の gRPC プロキシを生成する。
    service = create_service()

    # Network test requires PerfDog to install its helper apk on the device.
    # If the helper apk is already installed, please uninstall it manually first.
    # ネットワーク計測には PerfDog 補助 APK のインストールが必要。
    # 既にインストール済みの場合は手動でアンインストールしてから実行すること。
    service.enable_install_apk()

    # TODO:
    # Resolve the USB device by its serial id.
    # Use cmds.py "getdevices" / "getapps" to discover ids and packages.
    # シリアル ID で USB 端末を解決する。
    # 利用可能な ID やパッケージは cmds.py の "getdevices" / "getapps" で確認できる。
    device = service.get_usb_device('-')
    if device is None:
        logging.error("device not found")
        return

    run_test_app(device, '-', create_templates(service))


def run_test_app(device, package_name, templates):
    # Create the Test object that owns the lifecycle of one collection session.
    # 1 回の計測セッションのライフサイクルを管理する Test オブジェクトを生成する。
    test = Test(device)

    # Build the test target. The first template is applied at start time.
    # 計測対象を生成する。最初のテンプレートが計測開始時に適用される。
    builder = test.create_test_target_builder(TestAppBuilder)
    builder.set_package_name(package_name)
    builder.set_profiling_mode(perfdog_pb2.NETWORK)
    builder.set_network_template(templates[0])
    # Whether to relaunch the target app at start time. Default: True.
    # 計測開始時に対象アプリを再起動するか。既定: True。
    # builder.set_app_restarted(True)
    # Whether delay effects accumulate. Default: True. iOS does not support this yet.
    # 遅延効果を重ね合わせるか。既定: True。iOS は未対応。
    # builder.set_delay_overlay(True)
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

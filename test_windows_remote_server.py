# coding: utf-8

# =============================================================================
# Multi-device looped Windows performance test driver.
# One Service proxy manages multiple Windows Devices in parallel via threads.
# Designed to run from a "remote collector" host that drives several PCs.
#
# 複数 Windows 端末向けループ計測ドライバ。
# 1 つの Service プロキシが、複数 Windows 端末をスレッド並列で管理する。
# 「リモート コレクタ」ホストから複数 PC を駆動する用途を想定。
# =============================================================================

import logging
import threading
import time
import sys
import signal
from concurrent.futures import ThreadPoolExecutor

import perfdog_pb2
from perfdog import Test, TestSysProcessBuilder
from test_base import create_service, get_all_types, set_floating_window


class MultiDeviceLoopTester:
    """Multi-device loop test manager.
    One Service manages multiple Devices in parallel.

    複数端末ループ計測マネージャ。
    1 つの Service が複数の Device を並列に管理する。
    """

    def __init__(self, port=23456):
        self.service = None
        self.port = port
        self.running = True
        # Per-device test thread future, keyed by device id.
        # 端末 ID をキーとする、端末ごとの計測スレッド Future。
        self.device_tests = {}

        # Install signal handlers so Ctrl-C / kill cleanly stop every test.
        # シグナルハンドラを登録し、Ctrl-C / kill で全計測を確実に停止する。
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle termination signals.
        終了シグナルを処理する。
        """
        logging.info(f"Received signal {signum}, stopping all tests...")
        self.stop_all_tests()
        sys.exit(0)

    def initialize_service(self):
        """Initialize the PerfDogService proxy.
        PerfDogService プロキシを初期化する。
        """
        try:
            self.service = create_service(port=self.port)
            logging.info(f"Service initialized successfully on port {self.port}")
            return True
        except Exception as e:
            logging.error(f"Failed to initialize service on port {self.port}: {e}")
            return False

    def get_windows_devices(self):
        """Return every Windows device discovered by the service.
        Service が検出した全 Windows 端末を返す。
        """
        if not self.service:
            return []

        windows_devices = []
        try:
            for device in self.service.get_devices():
                if device.os_type() == perfdog_pb2.WINDOWS:
                    windows_devices.append(device)
        except Exception as e:
            logging.error(f"Failed to get devices: {e}")

        return windows_devices

    def get_device_by_id(self, device_id):
        """Resolve a device by its uid.
        UID から端末を解決する。
        """
        windows_devices = self.get_windows_devices()
        for device in windows_devices:
            if device.uid() == device_id:
                logging.info(f"Found device: {device.name()}, UID: {device.uid()}")
                return device
        return None

    def refresh_devices(self):
        """Refresh the remote Windows device list.
        リモート Windows 端末一覧を更新する。
        """
        try:
            self.service.update_remote_windows_device()
            logging.info("Device list refreshed")
        except Exception as e:
            logging.warning(f"Failed to refresh devices: {e}")

    def list_all_devices(self):
        """List every available Windows device with its access type.
        全ての利用可能な Windows 端末をアクセスタイプ付きで一覧表示する。
        """
        self.refresh_devices()
        windows_devices = self.get_windows_devices()

        logging.info(f"Found {len(windows_devices)} Windows devices:")
        for i, device in enumerate(windows_devices):
            try:
                real_dev = device.real_device()
                access_type_info = "Unknown"

                # Read the access type field if available.
                # アクセスタイプフィールドが存在すれば読み出す。
                if hasattr(real_dev, 'accessType'):
                    access_type_raw = real_dev.accessType
                elif hasattr(real_dev, 'access_type'):
                    access_type_raw = real_dev.access_type
                else:
                    access_type_raw = None

                # Convert to a human-readable string.
                # 人間が読める文字列に変換する。
                if access_type_raw is not None:
                    if access_type_raw == perfdog_pb2.LOCAL:
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

                logging.info(f"  Device {i+1}: Name={device.name()}, UID={device.uid()}, AccessType={access_type_info}")

            except Exception as e:
                logging.warning(f"Failed to get info for device {i+1}: {e}")

        return windows_devices

    def run_device_loop_test(self, device_config):
        """Run a looped test against a single device.
        1 端末に対するループ計測を実行する。
        """
        device_id = device_config['device_id']
        pid = device_config['pid']
        test_duration = device_config.get('test_duration', 30)
        cycle_interval = device_config.get('cycle_interval', 10)
        # max_cycles == -1 means run forever until shutdown.
        # max_cycles == -1 は停止指示まで無限ループを意味する。
        max_cycles = device_config.get('max_cycles', -1)

        thread_id = threading.current_thread().ident
        logging.info(f"[Device-{device_id}] Starting loop test in thread {thread_id}")
        logging.info(f"[Device-{device_id}] Config: Duration={test_duration}s, Interval={cycle_interval}s, MaxCycles={max_cycles}")

        # Resolve the target device, retrying a few times if not yet visible.
        # 対象端末を解決する。一覧に未出現の場合は数回リトライする。
        device = None
        max_retries = 5
        retry_count = 0

        while device is None and retry_count < max_retries and self.running:
            self.refresh_devices()
            device = self.get_device_by_id(device_id)

            if device is None:
                retry_count += 1
                logging.warning(f"[Device-{device_id}] Device not found, retrying... ({retry_count}/{max_retries})")
                time.sleep(2)
            else:
                logging.info(f"[Device-{device_id}] Connected to device: {device.name()}")
                break

        if device is None:
            logging.error(f"[Device-{device_id}] Device not found after retries")
            return

        # Begin the loop.
        # ループを開始する。
        test_cycle = 1
        while self.running and (max_cycles == -1 or test_cycle <= max_cycles):
            logging.info(f"[Device-{device_id}] === Starting Test Cycle {test_cycle} ===")

            test = None
            try:
                # Create the Test object for this cycle.
                # 当サイクル用の Test オブジェクトを生成する。
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Creating Test object...")
                test = Test(device)
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Test object created successfully")

                # Wire callbacks.
                # コールバックを登録する。
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Setting up callbacks...")
                evt = threading.Event()
                test.set_first_perf_data_callback(lambda: evt.set())
                test.set_perf_data_callback(lambda perf_data: logging.debug(f"[Device-{device_id}] PerfData: {perf_data}"))
                test.set_error_perf_data_callback(lambda perf_data: logging.error(f"[Device-{device_id}] PerfDog Error: %s", perf_data.errorData.msg))
                test.set_warning_perf_data_callback(lambda perf_data: logging.warning(f"[Device-{device_id}] PerfDog Warning: %s", perf_data.warningData.msg))

                # Hide the on-device floating overlay.
                # 端末上のフローティング表示を非表示にする。
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Configuring floating window...")
                set_floating_window(device)

                # Verify the configured PID exists before starting.
                # 計測開始前に、指定 PID が実在することを確認する。
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Verifying PID {pid} exists...")
                try:
                    processes = device.get_sys_processes()
                    pid_exists = any(proc.pid == pid for proc in processes)
                    if not pid_exists:
                        logging.warning(f"[Device-{device_id}] Cycle {test_cycle}: PID {pid} not found in process list")
                        # Show the first 10 processes for reference.
                        # 参考として先頭 10 件のプロセスを表示する。
                        logging.info(f"[Device-{device_id}] Available processes (first 10):")
                        for i, proc in enumerate(processes[:10]):
                            logging.info(f"[Device-{device_id}]   PID {proc.pid}: {proc.name}")
                    else:
                        logging.info(f"[Device-{device_id}] Cycle {test_cycle}: PID {pid} found in process list")
                except Exception as e:
                    logging.warning(f"[Device-{device_id}] Cycle {test_cycle}: Could not verify PID: {str(e)}")

                # Build the test target.
                # 計測対象を生成する。
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Creating test target for PID {pid}...")
                builder = test.create_test_target_builder(TestSysProcessBuilder)
                builder.set_pid(pid)
                builder.set_dx_version(perfdog_pb2.AUTO)

                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Building test target...")
                test.set_test_target(builder.build())

                # TODO: Configure metric types.
                # TODO: 計測指標を設定する。
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Setting test types...")
                # test.set_types(perfdog_pb2.FPS, perfdog_pb2.FRAME_TIME, perfdog_pb2.WINDOWS_CPU, perfdog_pb2.WINDOWS_MEMORY)
                types, dynamic_types = get_all_types(device)

                if types is not None:
                    test.set_types(*types)

                if dynamic_types is not None:
                    test.set_dynamic_types(*dynamic_types)

                # Begin performance data collection.
                # 性能データの収集を開始する。
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Starting performance data collection...")
                test.start()

                # Wait up to 30 seconds for the first sample.
                # 最初のサンプルが届くまで最大 30 秒待機する。
                if evt.wait(timeout=30):
                    logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Performance data collection started")

                    # Run one cycle worth of automation steps.
                    # 1 サイクル分の自動化操作を実行する。
                    self.run_test_cycle(test, device_id, test_cycle, test_duration)

                    # Stop and persist results.
                    # 計測停止と結果保存。
                    test.stop()
                    case_name = f"device_{device_id[-8:]}_cycle_{test_cycle}_{int(time.time())}"
                    test.save_data(case_name=case_name)
                    logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Test completed, data saved as {case_name}")

                else:
                    logging.warning(f"[Device-{device_id}] Cycle {test_cycle}: Timeout waiting for performance data")

                test_cycle += 1

            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                logging.error(f"[Device-{device_id}] Cycle {test_cycle}: Test failed: {str(e)}")
                logging.error(f"[Device-{device_id}] Cycle {test_cycle}: Error details:{error_details}")
            finally:
                # Clean up resources.
                # リソースを解放する。
                try:
                    if test and test.is_start():
                        test.stop()
                        logging.debug(f"[Device-{device_id}] Test stopped in finally block")
                except Exception as e:
                    logging.error(f"[Device-{device_id}] Error stopping test: {str(e)}")

            # Should we continue?
            # 継続するか判定する。
            if not self.running:
                break

            if max_cycles > 0 and test_cycle > max_cycles:
                logging.info(f"[Device-{device_id}] Reached maximum cycles ({max_cycles})")
                break

            # Sleep between cycles, but stay responsive to shutdown.
            # サイクル間のスリープ。停止指示に素早く反応できるよう小刻みに待機する。
            if self.running and (max_cycles == -1 or test_cycle <= max_cycles):
                logging.info(f"[Device-{device_id}] Cycle {test_cycle-1}: Waiting {cycle_interval}s before next cycle...")
                for i in range(cycle_interval):
                    if not self.running:
                        break
                    time.sleep(1)

        logging.info(f"[Device-{device_id}] Loop test completed after {test_cycle-1} cycles")

    # TODO: Customize this method to fit your real automation needs.
    # TODO: 実際の自動化要件に合わせて、このメソッドをカスタマイズする。
    def run_test_cycle(self, test, device_id, cycle, duration):
        """Run a single test cycle: sleep / set_label / add_note / sleep.
        1 サイクル分の操作（待機 / ラベル / メモ / 待機）を実行する。
        """
        logging.info(f"[Device-{device_id}] Cycle {cycle}: Running test for {duration} seconds...")

        # Compute label / note timestamps from the configured duration.
        # 設定された duration からラベル / メモのタイムスタンプを動的に計算する。
        label_time = max(5, duration // 3)
        note_time = max(10, duration * 2 // 3)

        # Add label.
        # ラベルを追加する。
        if duration > label_time:
            time.sleep(label_time)
            test.set_label(f'cycle_{cycle}_label')
            logging.info(f"[Device-{device_id}] Cycle {cycle}: Added label at {label_time}s")

            # Add note.
            # メモを追加する。
            if duration > note_time:
                time.sleep(note_time - label_time)
                test.add_note(f'cycle_{cycle}_note', note_time * 1000)
                logging.info(f"[Device-{device_id}] Cycle {cycle}: Added note at {note_time}s")

                # Remaining time.
                # 残り時間を消費する。
                time.sleep(duration - note_time)
            else:
                time.sleep(duration - label_time)
        else:
            time.sleep(duration)

    def start_multi_device_test(self, device_configs):
        """Launch the multi-device test.
        複数端末計測を開始する。
        """
        if not self.initialize_service():
            return False

        # List every available device for visibility.
        # 視認性のため、利用可能な端末を一覧表示する。
        self.list_all_devices()

        logging.info(f"Starting tests for {len(device_configs)} devices...")

        # Drive each device on its own thread.
        # 各端末を個別のスレッドで駆動する。
        with ThreadPoolExecutor(max_workers=len(device_configs)) as executor:
            futures = []

            for config in device_configs:
                future = executor.submit(self.run_device_loop_test, config)
                futures.append((config['device_id'], future))
                self.device_tests[config['device_id']] = future
                logging.info(f"Started test for device {config['device_id']}")

            # Wait for every test to finish.
            # 全計測の完了を待機する。
            try:
                for device_id, future in futures:
                    try:
                        future.result()
                        logging.info(f"Device {device_id} test completed successfully")
                    except Exception as e:
                        logging.error(f"Device {device_id} test failed: {e}")
            except KeyboardInterrupt:
                logging.info("Received interrupt, stopping all tests...")
                self.running = False

        logging.info("All device tests completed")
        return True

    def stop_all_tests(self):
        """Stop every active test.
        実行中の計測をすべて停止する。
        """
        self.running = False
        logging.info("Stopping all device tests...")


def main():
    """Main entry point.
    メインエントリポイント。
    """
    logging.basicConfig(
        format="%(asctime)s-%(levelname)s-[MultiDevice]: %(message)s",
        level=logging.INFO
    )

    # Default Service port.
    # 既定の Service ポート。
    port = 23456

    # TODO: Configure the device list to fit your environment.
    # TODO: 実際の環境に合わせて端末リストを設定する。
    device_configs = [
        # {
        #     'device_id': 'BE3C2100-9BAA-11EC-8FF3-08A469D86200',
        #     'pid': 2700,
        #     'test_duration': 30,
        #     'cycle_interval': 10,
        #     'max_cycles': 5
        # },
        {
            'device_id': 'BE3C2100-9BAA-11EC-8FF3-08A469D86200',
            'pid': 30536,
            'test_duration': 60,
            'cycle_interval': 15,
            'max_cycles': 3
        },
        # {
        #     'device_id': '53CB4E4C-2F86-11B2-A85C-E0E77B66AC57',
        #     'pid': 2540,
        #     'test_duration': 60,
        #     'cycle_interval': 15,
        #     'max_cycles': 3
        # }

    ]

    # Build the multi-device tester.
    # マルチ端末テスターを生成する。
    tester = MultiDeviceLoopTester(port=port)

    # Run.
    # 実行する。
    success = tester.start_multi_device_test(device_configs)

    if success:
        logging.info("Multi-device loop test completed successfully")
    else:
        logging.error("Multi-device loop test failed")


if __name__ == '__main__':
    main()

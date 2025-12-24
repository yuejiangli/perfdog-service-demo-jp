# coding: utf-8

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
    """多设备循环测试管理器 - 一个Service管理多个Device / Multi-device loop test manager - one Service manages multiple Devices"""
    
    def __init__(self, port=23456):
        self.service = None
        self.port = port
        self.running = True
        self.device_tests = {}  # 存储每个设备的测试线程 / Store test threads for each device
        
        # 设置信号处理器 / Set signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """处理终止信号 / Handle termination signal"""
        logging.info(f"Received signal {signum}, stopping all tests...")
        self.stop_all_tests()
        sys.exit(0)
    
    def initialize_service(self):
        """初始化PerfDog服务 / Initialize PerfDog service"""
        try:
            self.service = create_service(port=self.port)
            logging.info(f"Service initialized successfully on port {self.port}")
            return True
        except Exception as e:
            logging.error(f"Failed to initialize service on port {self.port}: {e}")
            return False
    
    def get_windows_devices(self):
        """获取所有Windows设备 / Get all Windows devices"""
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
        """根据设备ID获取指定设备 / Get specific device by device ID"""
        windows_devices = self.get_windows_devices()
        for device in windows_devices:
            if device.uid() == device_id:
                logging.info(f"Found device: {device.name()}, UID: {device.uid()}")
                return device
        return None
    
    def refresh_devices(self):
        """刷新设备列表 / Refresh device list"""
        try:
            self.service.update_remote_windows_device()
            logging.info("Device list refreshed")
        except Exception as e:
            logging.warning(f"Failed to refresh devices: {e}")
    
    def list_all_devices(self):
        """列出所有可用设备 / List all available devices"""
        self.refresh_devices()
        windows_devices = self.get_windows_devices()
        
        logging.info(f"Found {len(windows_devices)} Windows devices:")
        for i, device in enumerate(windows_devices):
            try:
                real_dev = device.real_device()
                access_type_info = "Unknown"
                
                # 获取访问类型 / Get access type
                if hasattr(real_dev, 'accessType'):
                    access_type_raw = real_dev.accessType
                elif hasattr(real_dev, 'access_type'):
                    access_type_raw = real_dev.access_type
                else:
                    access_type_raw = None
                
                # 转换为可读字符串 / Convert to readable string
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
        """为单个设备运行循环测试 / Run loop test for a single device"""
        device_id = device_config['device_id']
        pid = device_config['pid']
        test_duration = device_config.get('test_duration', 30)
        cycle_interval = device_config.get('cycle_interval', 10)
        max_cycles = device_config.get('max_cycles', -1)
        
        thread_id = threading.current_thread().ident
        logging.info(f"[Device-{device_id}] Starting loop test in thread {thread_id}")
        logging.info(f"[Device-{device_id}] Config: Duration={test_duration}s, Interval={cycle_interval}s, MaxCycles={max_cycles}")
        
        # 获取设备对象 / Get device object
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
        
        # 开始循环测试 / Start loop test
        test_cycle = 1
        while self.running and (max_cycles == -1 or test_cycle <= max_cycles):
            logging.info(f"[Device-{device_id}] === Starting Test Cycle {test_cycle} ===")
            
            test = None
            try:
                # 创建测试对象 / Create test object
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Creating Test object...")
                test = Test(device)
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Test object created successfully")
                
                # 设置回调 / Set callbacks
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Setting up callbacks...")
                evt = threading.Event()
                test.set_first_perf_data_callback(lambda: evt.set())
                test.set_perf_data_callback(lambda perf_data: logging.debug(f"[Device-{device_id}] PerfData: {perf_data}"))
                test.set_error_perf_data_callback(lambda perf_data: logging.error(f"[Device-{device_id}] PerfDog Error: %s", perf_data.errorData.msg))
                test.set_warning_perf_data_callback(lambda perf_data: logging.warning(f"[Device-{device_id}] PerfDog Warning: %s", perf_data.warningData.msg))
                
                # 配置浮窗 / Configure floating window
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Configuring floating window...")
                set_floating_window(device)
                
                # 验证PID是否存在 / Verify if PID exists
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Verifying PID {pid} exists...")
                try:
                    processes = device.get_sys_processes()
                    pid_exists = any(proc.pid == pid for proc in processes)
                    if not pid_exists:
                        logging.warning(f"[Device-{device_id}] Cycle {test_cycle}: PID {pid} not found in process list")
                        # 显示前10个进程供参考 / Show first 10 processes for reference
                        logging.info(f"[Device-{device_id}] Available processes (first 10):")
                        for i, proc in enumerate(processes[:10]):
                            logging.info(f"[Device-{device_id}]   PID {proc.pid}: {proc.name}")
                    else:
                        logging.info(f"[Device-{device_id}] Cycle {test_cycle}: PID {pid} found in process list")
                except Exception as e:
                    logging.warning(f"[Device-{device_id}] Cycle {test_cycle}: Could not verify PID: {str(e)}")
                
                # 创建测试目标 / Create test target
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Creating test target for PID {pid}...")
                builder = test.create_test_target_builder(TestSysProcessBuilder)
                builder.set_pid(pid)
                builder.set_dx_version(perfdog_pb2.AUTO)
                
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Building test target...")
                test.set_test_target(builder.build())
                
                # TODO: 设置测试类型 / Set test types
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Setting test types...")
                # test.set_types(perfdog_pb2.FPS, perfdog_pb2.FRAME_TIME, perfdog_pb2.WINDOWS_CPU, perfdog_pb2.WINDOWS_MEMORY)
                types, dynamic_types = get_all_types(device)

                if types is not None:
                    test.set_types(*types)

                if dynamic_types is not None:
                    test.set_dynamic_types(*dynamic_types)
                    
                # 启动测试 / Start test
                logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Starting performance data collection...")
                test.start()
                
                # 等待第一个性能数据 / Wait for first performance data
                if evt.wait(timeout=30):
                    logging.info(f"[Device-{device_id}] Cycle {test_cycle}: Performance data collection started")
                    
                    # 运行测试周期
                    self.run_test_cycle(test, device_id, test_cycle, test_duration)
                    
                    # 停止测试并保存数据
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
                # 清理资源 / Clean up resources
                try:
                    if test and test.is_start():
                        test.stop()
                        logging.debug(f"[Device-{device_id}] Test stopped in finally block")
                except Exception as e:
                    logging.error(f"[Device-{device_id}] Error stopping test: {str(e)}")
            
            # 检查是否应该继续循环 / Check if should continue loop
            if not self.running:
                break
                
            if max_cycles > 0 and test_cycle > max_cycles:
                logging.info(f"[Device-{device_id}] Reached maximum cycles ({max_cycles})")
                break
            
            # 周期间隔 / Cycle interval
            if self.running and (max_cycles == -1 or test_cycle <= max_cycles):
                logging.info(f"[Device-{device_id}] Cycle {test_cycle-1}: Waiting {cycle_interval}s before next cycle...")
                for i in range(cycle_interval):
                    if not self.running:
                        break
                    time.sleep(1)
        
        logging.info(f"[Device-{device_id}] Loop test completed after {test_cycle-1} cycles")
    
    #  TODO: 根据自己的需求编写run_test_cycle方法 / Write run_test_cycle method according to your needs
    def run_test_cycle(self, test, device_id, cycle, duration):
        """运行单个测试周期 / Run a single test cycle"""
        logging.info(f"[Device-{device_id}] Cycle {cycle}: Running test for {duration} seconds...")
        
        # 动态计算标签和注释时间点 / Dynamically calculate label and note time points
        label_time = max(5, duration // 3)
        note_time = max(10, duration * 2 // 3)
        
        # 添加标签 / Add label
        if duration > label_time:
            time.sleep(label_time)
            test.set_label(f'cycle_{cycle}_label')
            logging.info(f"[Device-{device_id}] Cycle {cycle}: Added label at {label_time}s")
            
            # 添加注释 / Add note
            if duration > note_time:
                time.sleep(note_time - label_time)
                test.add_note(f'cycle_{cycle}_note', note_time * 1000)
                logging.info(f"[Device-{device_id}] Cycle {cycle}: Added note at {note_time}s")
                
                # 剩余时间 / Remaining time
                time.sleep(duration - note_time)
            else:
                time.sleep(duration - label_time)
        else:
            time.sleep(duration)
    
    def start_multi_device_test(self, device_configs):
        """启动多设备测试 / Start multi-device test"""
        if not self.initialize_service():
            return False
        
        # 列出所有可用设备 / List all available devices
        self.list_all_devices()
        
        logging.info(f"Starting tests for {len(device_configs)} devices...")
        
        # 使用线程池运行多个设备测试 / Use thread pool to run multiple device tests
        with ThreadPoolExecutor(max_workers=len(device_configs)) as executor:
            futures = []
            
            for config in device_configs:
                future = executor.submit(self.run_device_loop_test, config)
                futures.append((config['device_id'], future))
                self.device_tests[config['device_id']] = future
                logging.info(f"Started test for device {config['device_id']}")
            
            # 等待所有测试完成 / Wait for all tests to complete
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
        """停止所有测试 / Stop all tests"""
        self.running = False
        logging.info("Stopping all device tests...")


def main():
    """主函数 / Main function"""
    logging.basicConfig(
        format="%(asctime)s-%(levelname)s-[MultiDevice]: %(message)s",
        level=logging.INFO
    )
    
    # 使用默认端口 / Use default port
    port = 23456
    
    # 配置多设备测试 / Configure multi-device test
    # TODO: 根据实际需要配置设备 / Configure devices according to actual needs
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
    
    # 创建多设备测试器 / Create multi-device tester
    tester = MultiDeviceLoopTester(port=port)
    
    # 启动测试 / Start test
    success = tester.start_multi_device_test(device_configs)
    
    if success:
        logging.info("Multi-device loop test completed successfully")
    else:
        logging.error("Multi-device loop test failed")


if __name__ == '__main__':
    main()
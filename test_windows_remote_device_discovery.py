# coding: utf-8

import logging
import sys
import time
import perfdog_pb2
from test_base import create_service

def discover_devices(port=23456):
    """发现并显示所有可用设备 / Discover and display all available devices"""
    
    logging.basicConfig(
        format="%(asctime)s-%(levelname)s: %(message)s",
        level=logging.INFO
    )
    
    print("=== PerfDog 设备发现工具 ===")
    print()
    
    # 创建服务 / Create service
    try:
        service = create_service(port=port)
        logging.info(f"Service connected successfully on port {port}")
    except Exception as e:
        logging.error(f"Failed to connect to PerfDog service on port {port}: {e}")
        return []
    
    # 刷新远程设备列表 / Refresh remote device list
    try:
        logging.info("Refreshing remote device list...")
        service.update_remote_windows_device()
        time.sleep(2)  # 等待设备列表更新 / Wait for device list update
    except Exception as e:
        logging.warning(f"Failed to refresh remote devices: {e}")
    
    # 获取所有设备 / Get all devices
    try:
        all_devices = service.get_devices()
        logging.info(f"Found {len(all_devices)} total devices")
    except Exception as e:
        logging.error(f"Failed to get device list: {e}")
        return []
    
    # 筛选Windows设备 / Filter Windows devices
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
            
            # 获取访问类型 / Get access type
            if hasattr(real_dev, 'accessType'):
                access_type_raw = real_dev.accessType
            elif hasattr(real_dev, 'access_type'):
                access_type_raw = real_dev.access_type
            
            # 转换为可读字符串 / Convert to readable string
            if access_type_raw is not None:
                if access_type_raw == perfdog_pb2.LOCAL:
                    # 如果设备名称包含Remote但access_type是LOCAL，说明是远程设备的本地代理
                    # If device name contains Remote but access_type is LOCAL, it's a local proxy for remote device
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
            
            # 连接类型 - 对于远程设备，更准确地显示连接类型
            # Connection type - display connection type more accurately for remote devices
            conn_type = device.conn_type()
            if "(Remote)" in device.name():
                # 远程设备通过网络连接到本地PerfDog服务
                # Remote devices connect to local PerfDog service via network
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
    """交互式模式 / Interactive mode"""
    
    # 发现设备 / Discover devices
    devices = discover_devices()
    if not devices:
        return
    
    while True:
        print("\n=== 操作选项 ===")
        print("1. 生成设备配置代码")
        print("2. 重新扫描设备")
        print("3. 退出")
        
        choice = input("\n请选择操作 (1-3): ").strip()
        
        if choice == '1':
            # 生成配置代码 / Generate configuration code
            print("\n=== 生成设备配置 ===")
            selected_devices = input("请输入要配置的设备编号 (用逗号分隔，如: 1,2,3): ").strip()
            
            try:
                device_indices = [int(x.strip()) - 1 for x in selected_devices.split(',')]
                generate_config_code(devices, device_indices)
            except ValueError:
                print("请输入有效的设备编号")
        
        elif choice == '2':
            # 重新扫描 / Rescan devices
            devices = discover_devices()
            if not devices:
                break
        
        elif choice == '3':
            print("退出设备发现工具")
            break
        
        else:
            print("无效选择，请重新输入")

def generate_config_code(devices, device_indices):
    """生成设备配置代码 / Generate device configuration code"""
    
    print("\n=== 生成的设备配置代码 ===")
    print()
    
    for i, index in enumerate(device_indices):
        if 0 <= index < len(devices):
            device_info = devices[index]
            
            # 获取默认PID（可以提示用户输入）
            pid_input = input(f"请输入设备 '{device_info['name']}' 要测试的进程PID: ").strip()
            try:
                pid = int(pid_input)
            except ValueError:
                pid = 1234  # 默认值
                print(f"使用默认PID: {pid}")
            
            print(f"        {{")
            print(f"            'device_id': '{device_info['uid']}',")
            print(f"            'pid': {pid},")
            print(f"            'test_duration': 60,")
            print(f"            'cycle_interval': 15,")
            print(f"            'max_cycles': 3")
            print(f"        }},")
            
            if i < len(device_indices) - 1:
                print()
    
    print("\n=== 配置代码生成完成 ===")

def main():
    """主函数"""
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--list':
            # 只列出设备
            discover_devices()
        elif sys.argv[1] == '--port' and len(sys.argv) > 2:
            # 指定端口
            try:
                port = int(sys.argv[2])
                discover_devices(port)
            except ValueError:
                print("Invalid port number")
        else:
            print("Usage: python device_discovery.py [--list] [--port PORT_NUMBER]")
    else:
        # 交互式模式
        interactive_mode()

if __name__ == '__main__':
    main()
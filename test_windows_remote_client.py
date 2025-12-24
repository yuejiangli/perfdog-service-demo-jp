# coding: utf-8

import logging
import time

import perfdog_pb2
from test_base import create_service


def get_windows_device(service):
    for device in service.get_devices():
        if device.os_type() == perfdog_pb2.WINDOWS:
            return device
    return None


def main():
    # Log output configuration, you can configure it yourself if you have special needs
    # 日志输出配置，如果有特别的需要可自行配置 / Log output configuration, configure yourself if needed
    logging.basicConfig(format="%(asctime)s-%(levelname)s: %(message)s", level=logging.INFO)

    # Create service object proxy
    # 创建服务对象代理 / Create service object proxy
    service = create_service()

    # Get the device object
    # 获取设备对象 / Get device object
    while True:
        # 刷新远程电脑列表 / Refresh remote computer list
        service.update_remote_windows_device()
        # 获取远程电脑对象 / Get remote computer object
        device = get_windows_device(service)
        if device is None:
            logging.error("non-exist device")
            return
        time.sleep(2)


        
   
if __name__ == '__main__':
    main()

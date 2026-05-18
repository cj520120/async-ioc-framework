import asyncio
import logging
import signal
import time
from pathlib import Path
from typing import List, Optional, Union

from ioc import ApplicationContext

logger = logging.getLogger(__name__)


async def run_async(config_file: str, base_path: Union[Path, str], modules: Optional[List[str]] = None, **kwargs):
    """
    启动 IoC 容器，扫描并加载组件，等待退出信号后优雅关闭。

    :param config_file: 配置文件路径（YAML）
    :param base_path: 项目根目录（扫描模块时的基准路径）
    :param modules: 需要显式扫描的模块名列表（可选）
    """
    start_time = time.perf_counter()

    # 1. 初始化配置
    ApplicationContext.initialize(config_file=config_file)
    logger.info(f"配置文件加载完成: {config_file}")

    # 2. 扫描显式传入的模块
    if modules:
        for module in modules:
            ApplicationContext.scan_directory(base_path, base_package=module)
            logger.debug(f"已扫描模块: {module}")

    # 3. 扫描配置文件中声明的模块
    config_modules = ApplicationContext.get_app_config().get("modules", [])
    if config_modules:
        for module in config_modules:
            ApplicationContext.scan_directory(base_path, base_package=module)
            logger.debug(f"已扫描配置模块: {module}")

    # 4. 刷新容器（创建所有非懒加载 Bean，启动调度器）
    await ApplicationContext.refresh()
    logger.info(f"容器刷新完成，耗时 {time.perf_counter() - start_time:.3f}s")

    # 5. 优雅关闭信号处理
    stop_event = asyncio.Event()

    def _handle_signal(signum, frame):
        logger.info(f"收到信号 {signum}，准备关闭服务...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal, sig, None)

    logger.info("所有服务启动完成，等待停止信号...")
    await stop_event.wait()

    # 6. 关闭容器
    logger.info("开始关闭容器...")
    await ApplicationContext.close()
    logger.info("所有服务已关闭")

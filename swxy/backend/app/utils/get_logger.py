"""
===========================================================================
📌 utils/get_logger.py — 日志工具（带颜色的控制台日志）
===========================================================================

🔰 新手导读：
日志是开发中非常重要的调试和监控手段。
这个文件创建了一个"彩色日志器"，不同级别的日志用不同颜色显示：
  - DEBUG（调试）→ 青色
  - INFO（信息）→ 绿色
  - WARNING（警告）→ 黄色
  - ERROR（错误）→ 红色
  - CRITICAL（严重）→ 红底白字

💡 使用方式：
  from utils import logger
  logger.info("这是一条普通信息")
  logger.error("这是一条错误信息")
===========================================================================
"""

import logging
import colorlog  # colorlog: 第三方库，给日志输出添加颜色
import os


def get_logger():
    """创建并返回一个带颜色输出的日志器"""

    # 从环境变量读取日志级别，默认为 INFO
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEFAULT')

    # ==================== 配置彩色日志格式 ====================
    handler = colorlog.StreamHandler()  # 日志输出到控制台
    formatter = colorlog.ColoredFormatter(
        # 日志格式：颜色 + 时间 + 级别 + 函数名 + 消息内容
        "%(log_color)s%(asctime)s.%(msecs)03d - %(levelname)s - [%(funcName)s] - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',       # 调试信息 → 青色
            'INFO': 'green',       # 普通信息 → 绿色
            'WARNING': 'yellow',   # 警告 → 黄色
            'ERROR': 'red',        # 错误 → 红色
            'CRITICAL': 'red,bg_white',  # 严重错误 → 红底白字
        }
    )
    handler.setFormatter(formatter)

    # ==================== 创建日志器实例 ====================
    logger = colorlog.getLogger(__name__)
    logger.addHandler(handler)

    # 设置日志级别
    LOG_LEVEL_OPTION = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
        'DEFAULT': logging.INFO  # 默认 INFO 级别
    }
    logger.setLevel(LOG_LEVEL_OPTION.get(LOG_LEVEL.upper(), 'DEFAULT'))

    return logger

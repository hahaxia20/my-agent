# src/core/logging_config.py
import logging
import logging.handlers
import sys
from typing import Optional
from datetime import datetime
import json

# ====================== 日志格式定义 ======================

# 彩色日志格式（用于控制台）
COLOR_FORMAT = {
    'DEBUG': '\033[36m',  # 青色
    'INFO': '\033[32m',  # 绿色
    'WARNING': '\033[33m',  # 黄色
    'ERROR': '\033[31m',  # 红色
    'CRITICAL': '\033[35m',  # 紫色
    'RESET': '\033[0m'  # 重置
}


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""

    def format(self, record):
        levelname = record.levelname
        if levelname in COLOR_FORMAT:
            record.levelname = f"{COLOR_FORMAT[levelname]}{levelname}{COLOR_FORMAT['RESET']}"
            record.name = f"\033[36m{record.name}\033[0m"

        # 添加 emoji 标识
        if hasattr(record, 'emoji'):
            record.emoji = getattr(record, 'emoji', '')

        return super().format(record)


class JsonFormatter(logging.Formatter):
    """JSON 格式日志（用于文件）"""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # 添加异常信息
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # 添加自定义字段
        if hasattr(record, 'session_id'):
            log_entry["session_id"] = record.session_id
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        if hasattr(record, 'tool_name'):
            log_entry["tool_name"] = record.tool_name
        if hasattr(record, 'duration'):
            log_entry["duration"] = record.duration

        return json.dumps(log_entry, ensure_ascii=False)


# ====================== 日志配置 ======================

def setup_logging(
        log_level: str = "INFO",
        log_to_file: bool = True,
        log_to_console: bool = True,
        log_file_path: str = "logs/agent.log",
        json_format: bool = False,
        enable_emoji: bool = True
) -> None:
    """
    配置日志系统

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: 是否输出到文件
        log_to_console: 是否输出到控制台
        log_file_path: 日志文件路径
        json_format: 是否使用 JSON 格式
        enable_emoji: 是否启用 emoji（仅控制台）
    """

    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # 清除现有的处理器
    root_logger.handlers.clear()

    # 控制台处理器
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))

        if json_format:
            console_formatter = JsonFormatter()
        else:
            # 控制台使用彩色格式
            console_format = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
            if enable_emoji:
                console_format = '%(asctime)s | %(levelname)-8s | %(message)s'
            console_formatter = ColoredFormatter(console_format)

        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # 文件处理器
    if log_to_file:
        import os
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别

        if json_format:
            file_formatter = JsonFormatter()
        else:
            file_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # 设置第三方库的日志级别（减少噪音）
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("langgraph").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    # 记录启动信息
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("日志系统已初始化")
    logger.info(f"  日志级别: {log_level}")
    logger.info(f"  控制台输出: {log_to_console}")
    logger.info(f"  文件输出: {log_to_file} -> {log_file_path}")
    logger.info(f"  JSON格式: {json_format}")
    logger.info("=" * 60)


# ====================== 日志辅助函数 ======================

def get_logger(name: str, emoji: Optional[str] = None):
    """获取带 emoji 的日志记录器"""
    logger = logging.getLogger(name)

    # 添加 emoji 到日志消息
    if emoji:
        original_log = logger._log

        def _log_with_emoji(level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):
            if extra is None:
                extra = {}
            extra['emoji'] = emoji
            original_log(level, msg, args, exc_info, extra, stack_info, stacklevel + 1)

        logger._log = _log_with_emoji.__get__(logger, type(logger))

    return logger


class LoggerContext:
    """日志上下文管理器"""

    def __init__(self, logger, session_id: str = None, user_id: str = None):
        self.logger = logger
        self.session_id = session_id
        self.user_id = user_id
        self.old_extra = {}

    def __enter__(self):
        # 保存旧的 extra
        if hasattr(self.logger, '_extra'):
            self.old_extra = self.logger._extra

        # 设置新的 extra
        self.logger._extra = {
            'session_id': self.session_id,
            'user_id': self.user_id
        }
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 恢复旧的 extra
        if self.old_extra:
            self.logger._extra = self.old_extra
        else:
            delattr(self.logger, '_extra')


# ====================== 日志过滤器和处理器 ======================

class ToolCallFilter(logging.Filter):
    """工具调用日志过滤器"""

    def filter(self, record):
        # 只记录工具和技能相关的日志
        if hasattr(record, 'tool_name') or hasattr(record, 'skill_name'):
            return True
        return '工具' in record.getMessage() or '技能' in record.getMessage()


class SessionFilter(logging.Filter):
    """会话过滤器"""

    def __init__(self, session_id: str):
        self.session_id = session_id

    def filter(self, record):
        if hasattr(record, 'session_id'):
            return record.session_id == self.session_id
        return True


# ====================== 日志轮转 ======================

class RotatingFileHandlerWithBackup(logging.handlers.RotatingFileHandler):
    """支持备份的轮转文件处理器"""

    def __init__(self, filename, mode='a', maxBytes=0, backupCount=5, encoding=None, delay=False):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)

    def doRollover(self):
        """执行日志轮转时记录信息"""
        if self.stream:
            self.stream.close()
            self.stream = None

        # 记录轮转事件
        logger = logging.getLogger(__name__)
        logger.info(f"日志文件轮转: {self.baseFilename}")

        super().doRollover()


# ====================== 初始化配置 ======================

def init_logging_from_settings():
    """从配置文件初始化日志"""
    try:
        from src.config import get_settings_safe
        settings = get_settings_safe()

        log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
        log_to_file = getattr(settings, 'LOG_TO_FILE', True)
        log_to_console = getattr(settings, 'LOG_TO_CONSOLE', True)
        log_file_path = getattr(settings, 'LOG_FILE_PATH', 'logs/agent.log')
        json_format = getattr(settings, 'LOG_JSON_FORMAT', False)
        enable_emoji = getattr(settings, 'LOG_ENABLE_EMOJI', True)

        setup_logging(
            log_level=log_level,
            log_to_file=log_to_file,
            log_to_console=log_to_console,
            log_file_path=log_file_path,
            json_format=json_format,
            enable_emoji=enable_emoji
        )
    except Exception as e:
        # 如果配置加载失败，使用默认配置
        setup_logging(log_level="INFO", log_to_console=True, log_to_file=False)


# ====================== 使用示例 ======================
if __name__ == "__main__":
    # 快速测试
    setup_logging(log_level="DEBUG", log_to_console=True, log_to_file=False)

    logger = logging.getLogger("test")
    logger.debug("这是调试信息")
    logger.info("这是普通信息")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")
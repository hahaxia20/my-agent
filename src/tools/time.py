"""
时间查询工具 - 生产级实现
"""
from src.tools.base import BaseTool
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import logging
import time
import pytz

logger = logging.getLogger(__name__)


class TimeTool(BaseTool):
    """生产级时间查询工具 - 支持时区和自定义格式"""

    def __init__(self):
        super().__init__()
        self.name = "get_current_time"
        self.description = "获取当前日期和时间（支持指定时区和格式）"

        self.parameters = {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "时区，如: Asia/Shanghai, America/New_York, Europe/London",
                    "default": "Asia/Shanghai"
                },
                "format": {
                    "type": "string",
                    "description": "输出格式，支持: timestamp(时间戳), ISO格式, 或自定义格式如 'YYYY-MM-DD HH:mm:ss'",
                    "default": "YYYY-MM-DD HH:mm:ss"
                }
            }
        }

        self.timeout = 2  # 时间查询快速响应
        self.retry_count = 1

        # 支持的时区列表（常用）
        self.common_timezones = {
            "shanghai": "Asia/Shanghai",
            "beijing": "Asia/Shanghai",
            "newyork": "America/New_York",
            "london": "Europe/London",
            "tokyo": "Asia/Tokyo",
            "paris": "Europe/Paris",
            "sydney": "Australia/Sydney",
            "la": "America/Los_Angeles",
            "utc": "UTC"
        }

    def _normalize_timezone(self, timezone_str: str) -> str:
        """标准化时区名称"""
        if not timezone_str:
            return "Asia/Shanghai"

        # 转换小写并去除空格
        normalized = timezone_str.lower().strip().replace(" ", "_")

        # 检查常见别名
        if normalized in self.common_timezones:
            return self.common_timezones[normalized]

        # 检查是否是有效时区
        if normalized in pytz.all_timezones:
            return normalized

        # 尝试添加 Asia/ 前缀（如 "shanghai" -> "Asia/Shanghai"）
        if normalized in [tz.split('/')[-1].lower() for tz in pytz.all_timezones if '/' in tz]:
            for tz in pytz.all_timezones:
                if '/' in tz and tz.split('/')[-1].lower() == normalized:
                    return tz

        # 默认返回上海时区
        logger.warning(f"未知时区: {timezone_str}, 使用默认时区 Asia/Shanghai")
        return "Asia/Shanghai"

    def _format_time(self, dt: datetime, format_str: str) -> str:
        """格式化时间"""
        # 处理特殊格式
        if format_str.lower() == "timestamp":
            return str(int(dt.timestamp()))

        if format_str.lower() == "iso":
            return dt.isoformat()

        # 自定义格式转换（按长度降序，避免短匹配覆盖长匹配）
        format_map = [
            ("YYYY", "%Y"),
            ("MM", "%m"),
            ("DD", "%d"),
            ("HH", "%H"),
            ("hh", "%I"),
            ("mm", "%M"),
            ("ss", "%S"),
            ("SSS", "%f"),
            ("ZZ", "%z"),
            ("A", "%p"),
        ]

        for key, value in format_map:
            format_str = format_str.replace(key, value)

        try:
            return dt.strftime(format_str)
        except ValueError as e:
            logger.warning(f"时间格式错误: {format_str}, 使用默认格式")
            return dt.strftime("%Y-%m-%d %H:%M:%S")

    async def execute(self, timezone: str = "Asia/Shanghai", format: str = "YYYY-MM-DD HH:mm:ss", **kwargs) -> dict:
        """获取当前时间"""
        try:
            start_time = time.time()

            # 标准化时区
            normalized_tz = self._normalize_timezone(timezone)

            logger.info(f"⏰ 获取时间: 时区={normalized_tz}, 格式={format}")

            # 获取时区对象
            try:
                tz = pytz.timezone(normalized_tz)
            except Exception as e:
                logger.warning(f"时区 {normalized_tz} 无效: {e}, 使用 UTC")
                tz = pytz.UTC

            # 获取当前时间
            now = datetime.now(tz)

            # 格式化输出
            formatted_time = self._format_time(now, format)

            # 构建详细信息
            result = {
                "success": True,
                "timezone": normalized_tz,
                "current_time": formatted_time,
                "timestamp": int(now.timestamp()),
                "iso_format": now.isoformat(),
                "year": now.year,
                "month": now.month,
                "day": now.day,
                "hour": now.hour,
                "minute": now.minute,
                "second": now.second,
                "weekday": now.strftime("%A"),
                "weekday_number": now.weekday(),
                "is_weekend": now.weekday() >= 5
            }

            execution_time = time.time() - start_time

            logger.info(f"✅ 时间获取成功: {formatted_time}, 耗时 {execution_time:.3f}s")

            return result

        except Exception as e:
            logger.error(f"时间获取失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"获取时间失败: {str(e)}",
                "current_time": None
            }

    async def get_time_difference(self, from_timezone: str, to_timezone: str) -> dict:
        """获取两个时区的时间差（额外功能）"""
        try:
            from_tz = pytz.timezone(self._normalize_timezone(from_timezone))
            to_tz = pytz.timezone(self._normalize_timezone(to_timezone))

            now = datetime.now()
            from_time = now.replace(tzinfo=from_tz)
            to_time = now.replace(tzinfo=to_tz)

            diff_seconds = to_time.utcoffset().total_seconds() - from_time.utcoffset().total_seconds()
            diff_hours = diff_seconds / 3600

            return {
                "success": True,
                "from_timezone": from_timezone,
                "to_timezone": to_timezone,
                "difference_hours": diff_hours,
                "difference_formatted": f"{int(diff_hours)}小时" if diff_hours == int(diff_hours) else f"{diff_hours}小时"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
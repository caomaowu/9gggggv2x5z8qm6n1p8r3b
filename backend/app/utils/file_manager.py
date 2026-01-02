"""
文件管理器 - 哈雷酱的智能文件管理！
负责临时文件的创建、清理和冲突避免
"""

import os
import uuid
import time
import threading
import shutil
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TempFileManager:
    """
    临时文件管理器

    哼哼！本小姐的文件管理器确保：
    - 零冲突的概率
    - 自动清理机制
    - 线程安全
    - 磁盘空间控制
    """

    def __init__(self, base_dir: str = "temp_charts", max_age_hours: int = 24, enable_thread: bool = True):
        """
        初始化文件管理器

        Args:
            base_dir: 临时文件基础目录
            max_age_hours: 文件最大保存时间（小时）
        """
        self.base_dir = Path(base_dir)
        self.max_age = timedelta(hours=max_age_hours)
        self._lock = threading.Lock()

        # 确保目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 记录当前会话的文件
        self.session_files: Dict[str, list] = {}

        if enable_thread:
            self._start_cleanup_thread()

        logger.debug(f"临时文件管理器初始化完成: {self.base_dir}")

    def generate_unique_filename(self, prefix: str = "", suffix: str = ".png") -> tuple:
        """
        生成唯一的文件名

        Args:
            prefix: 文件名前缀
            suffix: 文件名后缀

        Returns:
            tuple: (文件名, 完整路径)
        """
        # 使用时间戳 + UUID + 线程ID 确保绝对唯一
        timestamp = int(time.time() * 1000)  # 毫秒时间戳
        thread_id = threading.get_ident()
        unique_id = str(uuid.uuid4())[:8]

        # 构建文件名
        filename = f"{prefix}_{timestamp}_{thread_id}_{unique_id}{suffix}"
        filepath = self.base_dir / filename

        # 记录文件
        with self._lock:
            session_key = f"{timestamp}_{thread_id}"
            if session_key not in self.session_files:
                self.session_files[session_key] = []
            self.session_files[session_key].append(str(filepath))

        logger.debug(f"生成唯一文件名: {filename}")
        return filename, str(filepath)

    def create_session_dir(self, session_id: Optional[str] = None) -> Path:
        """
        为特定会话创建独立目录

        Args:
            session_id: 会话ID，如果为None则自动生成

        Returns:
            Path: 会话目录路径
        """
        if session_id is None:
            session_id = str(uuid.uuid4())[:12]

        session_dir = self.base_dir / f"session_{session_id}"
        session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"创建会话目录: {session_dir}")
        return session_dir

    def cleanup_old_files(self, force: bool = False) -> int:
        """
        清理过期文件

        Args:
            force: 是否强制清理所有文件

        Returns:
            int: 清理的文件数量
        """
        cleaned_count = 0
        current_time = datetime.now()

        with self._lock:
            try:
                for filepath in self.base_dir.rglob("*"):
                    if filepath.is_file():
                        if force:
                            filepath.unlink()
                            cleaned_count += 1
                            logger.debug(f"强制删除文件: {filepath}")
                        else:
                            # 检查文件修改时间
                            file_time = datetime.fromtimestamp(filepath.stat().st_mtime)
                            if current_time - file_time > self.max_age:
                                filepath.unlink()
                                cleaned_count += 1
                                logger.debug(f"删除过期文件: {filepath}")

                # 清理空目录
                for dirpath in sorted(self.base_dir.rglob("*"), reverse=True):
                    if dirpath.is_dir() and not any(dirpath.iterdir()):
                        dirpath.rmdir()
                        logger.debug(f"删除空目录: {dirpath}")

            except Exception as e:
                logger.error(f"清理文件时出错: {e}")

        if cleaned_count > 0:
            logger.info(f"清理完成，删除了 {cleaned_count} 个文件")

        return cleaned_count

    def cleanup_session_files(self, session_key: str) -> int:
        """
        清理特定会话的文件

        Args:
            session_key: 会话键

        Returns:
            int: 清理的文件数量
        """
        cleaned_count = 0

        with self._lock:
            if session_key in self.session_files:
                for filepath in self.session_files[session_key]:
                    try:
                        path = Path(filepath)
                        if path.exists():
                            path.unlink()
                            cleaned_count += 1
                            logger.debug(f"删除会话文件: {filepath}")
                    except Exception as e:
                        logger.error(f"删除会话文件失败 {filepath}: {e}")

                del self.session_files[session_key]

        return cleaned_count

    def get_directory_size(self) -> int:
        """
        获取临时目录大小（字节）

        Returns:
            int: 目录大小
        """
        total_size = 0
        try:
            for filepath in self.base_dir.rglob("*"):
                if filepath.is_file():
                    total_size += filepath.stat().st_size
        except Exception as e:
            logger.error(f"计算目录大小时出错: {e}")

        return total_size

    def get_file_count(self) -> int:
        """
        获取临时文件数量

        Returns:
            int: 文件数量
        """
        count = 0
        try:
            for filepath in self.base_dir.rglob("*"):
                if filepath.is_file():
                    count += 1
        except Exception as e:
            logger.error(f"统计文件数量时出错: {e}")

        return count

    def _start_cleanup_thread(self):
        """启动后台清理线程"""
        def cleanup_worker():
            while True:
                try:
                    # 每小时清理一次
                    time.sleep(3600)
                    self.cleanup_old_files()
                except Exception as e:
                    logger.error(f"后台清理线程出错: {e}")

        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.debug("后台清理线程已启动")


# 全局文件管理器实例
_file_manager: Optional[TempFileManager] = None


def get_file_manager() -> TempFileManager:
    """
    获取全局文件管理器实例

    Returns:
        TempFileManager: 文件管理器实例
    """
    global _file_manager
    if _file_manager is None:
        _file_manager = TempFileManager()
    return _file_manager


def cleanup_all_temp_files():
    """清理所有临时文件"""
    manager = get_file_manager()
    total = manager.cleanup_old_files(force=True)

    try:
        future_manager = TempFileManager(base_dir="future_charts", max_age_hours=168, enable_thread=False)
        total += future_manager.cleanup_old_files(force=True)
    except Exception as e:
        logger.error(f"清理 future_charts 时出错: {e}")

    return total


def get_temp_file_stats() -> dict:
    """
    获取临时文件统计信息

    Returns:
        dict: 统计信息
    """
    manager = get_file_manager()
    return {
        "file_count": manager.get_file_count(),
        "directory_size_mb": round(manager.get_directory_size() / (1024 * 1024), 2),
        "temp_directory": str(manager.base_dir)
    }
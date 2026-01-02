"""
Performance Monitor - 性能监控系统
重构后的性能监控模块，更清晰和高效
作者：哈雷酱（傲娇大小姐工程师）
"""

import time
import functools
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager
import os
import tracemalloc
try:
    import psutil
except Exception:
    psutil = None

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """
    性能监控器

    哼哼！本小姐把性能监控模块重构得更优雅了！
    """

    def __init__(self):
        """初始化性能监控器"""
        self.metrics: Dict[str, Any] = {}
        self.stage_stack: list = []
        self.start_time = time.time()
        self.enabled = True
        self._start_resources: Dict[str, Any] = {}
        self._end_resources: Dict[str, Any] = {}
        self._process = psutil.Process(os.getpid()) if psutil else None

    def _snapshot_resources(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        data["process_time"] = time.process_time()
        if self._process:
            try:
                data["cpu_percent"] = self._process.cpu_percent(interval=None)
                mem = self._process.memory_info()
                data["rss"] = getattr(mem, "rss", 0)
                data["vms"] = getattr(mem, "vms", 0)
            except Exception:
                pass
        try:
            if tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                data["tracemalloc_current"] = current
                data["tracemalloc_peak"] = peak
        except Exception:
            pass
        return data

    def start_monitoring(self):
        """开始性能监控"""
        self.start_time = time.time()
        self.metrics.clear()
        self.stage_stack.clear()
        try:
            if not tracemalloc.is_tracing():
                tracemalloc.start()
        except Exception:
            pass
        self._start_resources = self._snapshot_resources()
        logger.info("🔄 性能监控已启动")

    def end_monitoring(self) -> Dict[str, Any]:
        """结束性能监控并生成报告"""
        if not self.enabled:
            return {}

        total_time = time.time() - self.start_time
        self._end_resources = self._snapshot_resources()
        report = {
            "total_execution_time": total_time,
            "stages": self.metrics.copy(),
            "timestamp": datetime.now().isoformat()
        }
        if self._start_resources or self._end_resources:
            report["resources"] = {
                "start": self._start_resources,
                "end": self._end_resources
            }

        logger.info(f"📊 性能监控结束，总耗时: {total_time:.2f}秒")
        return report

    def record_stage(self, stage_name: str, execution_time: float, additional_data: Dict = None):
        """记录阶段执行时间"""
        if not self.enabled:
            return

        stage_data = {
            "execution_time": execution_time,
            "percentage": 0.0,  # 将在结束时计算
            "timestamp": datetime.now().isoformat()
        }

        if additional_data:
            stage_data.update(additional_data)

        self.metrics[stage_name] = stage_data

    def start_stage(self, stage_name: str):
        """开始一个阶段"""
        if not self.enabled:
            return

        start_time = time.time()
        resource_snapshot = self._snapshot_resources()
        self.stage_stack.append((stage_name, start_time, resource_snapshot))
        # 改为DEBUG级别，避免启动时的噪音日志
        logger.debug(f"🔄 开始执行: {stage_name}")

    def end_stage(self, stage_name: str = None) -> float:
        """结束当前阶段或指定阶段"""
        if not self.enabled or not self.stage_stack:
            return 0.0

        if stage_name:
            # 查找指定阶段
            for i, item in enumerate(self.stage_stack):
                name, start_time, res_start = item
                if name == stage_name:
                    execution_time = time.time() - start_time
                    self.stage_stack.pop(i)
                    res_end = self._snapshot_resources()
                    self.record_stage(stage_name, execution_time, {"resource_start": res_start, "resource_end": res_end})
                    # 只有执行时间大于0.01秒时才记录INFO日志，避免导入时的空执行噪音
                    if execution_time > 0.01:
                        logger.info(f"📊 [{stage_name}] 完成 - 耗时: {execution_time:.2f}秒")
                    return execution_time
        else:
            # 结束最后阶段
            name, start_time, res_start = self.stage_stack.pop()
            execution_time = time.time() - start_time
            res_end = self._snapshot_resources()
            self.record_stage(name, execution_time, {"resource_start": res_start, "resource_end": res_end})
            # 只有执行时间大于0.01秒时才记录INFO日志，避免导入时的空执行噪音
            if execution_time > 0.01:
                logger.info(f"📊 [{name}] 完成 - 耗时: {execution_time:.2f}秒")
            return execution_time

        return 0.0

    def calculate_percentages(self, total_time: float):
        """计算各阶段耗时占比"""
        if total_time <= 0:
            return

        for stage_name, stage_data in self.metrics.items():
            execution_time = stage_data["execution_time"]
            percentage = (execution_time / total_time) * 100
            stage_data["percentage"] = percentage
            logger.info(f"📊 [{stage_name}] 耗时: {execution_time:.2f}秒 (占比: {percentage:.1f}%)")

    def get_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        total_time = sum(stage["execution_time"] for stage in self.metrics.values())
        self.calculate_percentages(total_time)

        return {
            "total_time": total_time,
            "stage_count": len(self.metrics),
            "slowest_stage": max(self.metrics.items(), key=lambda x: x[1]["execution_time"])[0] if self.metrics else None,
            "fastest_stage": min(self.metrics.items(), key=lambda x: x[1]["execution_time"])[0] if self.metrics else None,
            "stages": self.metrics
        }

    def clear_metrics(self):
        """清空性能指标"""
        self.metrics.clear()
        self.stage_stack.clear()
        logger.info("性能指标已清空")

    def enable(self):
        """启用性能监控"""
        self.enabled = True
        logger.info("性能监控已启用")

    def disable(self):
        """禁用性能监控"""
        self.enabled = False
        logger.info("性能监控已禁用")


# 全局性能监控器实例
_global_monitor = PerformanceMonitor()


def performance_monitor(stage_name: str = None):
    """
    性能监控装饰器

    Args:
        stage_name: 阶段名称
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not _global_monitor.enabled:
                return func(*args, **kwargs)

            name = stage_name or f"{func.__module__}.{func.__name__}"
            _global_monitor.start_stage(name)

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                _global_monitor.end_stage(name)

        return wrapper
    return decorator


@contextmanager
def monitor_context(stage_name: str):
    """
    性能监控上下文管理器

    Args:
        stage_name: 阶段名称
    """
    if not _global_monitor.enabled:
        yield
        return

    _global_monitor.start_stage(stage_name)
    try:
        yield
    finally:
        _global_monitor.end_stage(stage_name)


def monitor_computation(operation_name: str):
    """
    计算过程监控装饰器

    Args:
        operation_name: 操作名称
    """
    return performance_monitor(f"计算: {operation_name}")


def monitor_llm_call(model_name: str = None):
    """
    LLM调用监控装饰器

    Args:
        model_name: 模型名称
    """
    name = f"LLM调用: {model_name}" if model_name else "LLM调用"
    return performance_monitor(name)


def monitor_image_generation(chart_type: str = None):
    """
    图像生成监控装饰器

    Args:
        chart_type: 图表类型
    """
    name = f"图像生成: {chart_type}" if chart_type else "图像生成"
    return performance_monitor(name)


def monitor_api_call(api_name: str = None):
    """
    API调用监控装饰器

    Args:
        api_name: API名称
    """
    name = f"API调用: {api_name}" if api_name else "API调用"
    return performance_monitor(name)


# 全局控制函数
def start_performance_monitoring():
    """开始全局性能监控"""
    _global_monitor.start_monitoring()


def end_performance_monitoring() -> Dict[str, Any]:
    """结束全局性能监控"""
    return _global_monitor.end_monitoring()


def get_performance_report() -> Dict[str, Any]:
    """获取性能报告"""
    return _global_monitor.get_summary()


def record_manual_stage(stage_name: str, execution_time: float, **kwargs):
    """手动记录阶段"""
    _global_monitor.record_stage(stage_name, execution_time, kwargs)


def enable_performance_monitoring():
    """启用性能监控"""
    _global_monitor.enable()


def disable_performance_monitoring():
    """禁用性能监控"""
    _global_monitor.disable()


def clear_performance_metrics():
    """清空性能指标"""
    _global_monitor.clear_metrics()


# 向后兼容的函数
def monitor_stage(stage_name: str):
    """监控阶段（向后兼容）"""
    return monitor_context(stage_name)


def record_stage_time(stage_name: str, execution_time: float):
    """记录阶段时间（向后兼容）"""
    record_manual_stage(stage_name, execution_time)
import threading
from typing import TypedDict, DefaultDict, List, Any, Tuple, cast
from hop_engine.config.constants import HopStatus
from collections import defaultdict

import functools
import time

# ==============================
# 线程局部存储工具类
# ==============================

# 定义重试上下文管理
class RetryContext:
    _local = threading.local()

    @classmethod
    def get_retry_count(cls):
        if not hasattr(cls._local, "retry_count"):
            cls._local.retry_count = 0
        return cls._local.retry_count

    @classmethod
    def set_retry_count(cls, count):
        cls._local.retry_count = count

    @classmethod
    def reset_retry_count(cls):
        if hasattr(cls._local, "retry_count"):
            cls._local.retry_count = 0

    @classmethod
    def log_retry_attempt(cls, status: HopStatus, result: Any):
        if not hasattr(cls._local, "retry_logs"):
            cls._local.retry_logs = []
        current_attempt = cls.get_retry_count() + 1
        cls._local.retry_logs.append(
            {
                "attempt": current_attempt,
                "status": str(status),
                "result": str(result),
            }
        )
        cls.set_retry_count(current_attempt)

    @classmethod
    def get_retry_logs(cls):
        return getattr(cls._local, "retry_logs", [])

    @classmethod
    def reset_retry_logs(cls):
        if hasattr(cls._local, "retry_logs"):
            cls._local.retry_logs = []


# 算子状态收集器
class FunctionStatusLogCollector:
    _local = threading.local()

    @classmethod
    def get_collector(cls):
        if not hasattr(cls._local, "status_log_collector"):
            cls._local.status_log_collector = []
        return cls._local.status_log_collector

    @classmethod
    def reset_collector(cls):
        cls._local.status_log_collector = []

    @classmethod
    def collect_status_log(cls, status: HopStatus, log: str):
        if hasattr(cls._local, "status_log_collector"):
            cls._local.status_log_collector.append((status, log))


# ==============================
# 统计数据类型定义
# ==============================

# 算子统计项的类型
class OperatorStat(TypedDict):
    calls: int
    success: int
    uncertain: int
    errors: int
    execution_times: List[float]
    min_time: float
    max_time: float
    retry_counts: List[int]
    total_retries: int


# 定义函数统计项的类型
class FunctionStat(TypedDict):
    calls: int
    success: int
    uncertain: int
    errors: int
    execution_times: List[float]
    function_status: HopStatus
    function_log: List[str]


# ==============================
# 核心统计类
# ==============================
class ExecutionStats:
    """执行统计管理器，支持线程隔离的嵌套会话统计

    该类实现了基于线程本地存储的会话栈管理，支持统计数据的层级合并。
    主要用于收集算子和函数的执行 metrics，包括调用次数、成功率、执行时间等。

    使用示例:
        with ExecutionStats() as stats:
            # 执行需要统计的代码
            stats.record_operator(...)
    """

    _thread_local = threading.local()

    def __init__(self):
        self._lock = threading.Lock()
        self._parent = None
        self.reset()

    def __enter__(self):
        if not hasattr(self._thread_local, "session_stack"):
            self._thread_local.session_stack = []

        if self._thread_local.session_stack:
            self._parent = self._thread_local.session_stack[-1]

        self._thread_local.session_stack.append(self)
        return self

    def __exit__(self, *args):
        self._thread_local.session_stack.pop()
        if not self._thread_local.session_stack:
            self.merge_to_global()
        else:
            self.merge_to_parent()

    def merge_to_global(self):
        with GLOBAL_STATS._lock:
            # 合并算子统计
            for op_name, session_op in self.operator_stats.items():
                global_op = GLOBAL_STATS.operator_stats[op_name]
                global_op["calls"] += session_op["calls"]
                global_op["success"] += session_op["success"]
                global_op["uncertain"] += session_op["uncertain"]
                global_op["errors"] += session_op["errors"]

                # 重试统计合并
                global_retries = global_op["retry_counts"]
                global_retries.extend(session_op["retry_counts"])
                if len(global_retries) > 100:
                    global_retries = global_retries[-100:]
                global_op["retry_counts"] = global_retries
                global_op["total_retries"] += session_op["total_retries"]

                # 时间统计合并
                global_times = global_op["execution_times"]
                global_times.extend(session_op["execution_times"])
                if len(global_times) > 100:
                    global_times = global_times[-100:]
                global_op["min_time"] = min(
                    global_op["min_time"], session_op["min_time"]
                )
                global_op["max_time"] = max(
                    global_op["max_time"], session_op["max_time"]
                )

            # 函数统计合并
            for func_name, session_func in self.function_stats.items():
                global_func = GLOBAL_STATS.function_stats[func_name]

                global_func["calls"] += session_func["calls"]
                global_func["success"] += session_func["success"]
                global_func["uncertain"] += session_func["uncertain"]
                global_func["errors"] += session_func["errors"]

                # 保留最近100条执行时间
                global_times = global_func["execution_times"]
                global_times.extend(session_func["execution_times"])
                if len(global_times) > 100:
                    global_times = global_times[-100:]

    def merge_to_parent(self):
        if self._parent:
            with self._lock, self._parent._lock:
                # 合并算子统计到父会话
                for op_name, session_op in self.operator_stats.items():
                    parent_op = self._parent.operator_stats[op_name]
                    parent_op["calls"] += session_op["calls"]
                    parent_op["success"] += session_op["success"]
                    parent_op["uncertain"] += session_op["uncertain"]
                    parent_op["errors"] += session_op["errors"]
                    parent_op["execution_times"].extend(session_op["execution_times"])
                    parent_op["retry_counts"].extend(session_op["retry_counts"])
                    parent_op["total_retries"] += session_op["total_retries"]
                    parent_op["min_time"] = min(
                        parent_op["min_time"], session_op["min_time"]
                    )
                    parent_op["max_time"] = max(
                        parent_op["max_time"], session_op["max_time"]
                    )

    def reset(self) -> None:
        # 算子级统计
        self.operator_stats: DefaultDict[str, OperatorStat] = defaultdict(
            lambda: {
                "calls": 0,
                "success": 0,
                "uncertain": 0,
                "errors": 0,
                "execution_times": [],
                "min_time": float("inf"),
                "max_time": 0.0,
                "retry_counts": [],
                "total_retries": 0,
            }
        )

        # 函数级统计
        self.function_stats: DefaultDict[str, FunctionStat] = defaultdict(
            lambda: {
                "calls": 0,
                "success": 0,
                "uncertain": 0,
                "errors": 0,
                "execution_times": [],
                "function_status": HopStatus.OK,  # 用于单次记录
                "function_log": [],  # 用于单次记录
            }
        )

    def record_operator(
        self,
        func_name: str,
        status: HopStatus,
        result: Any,
        duration: float,
        retry_count: int,
    ) -> None:
        """记录算子执行"""
        with self._lock:
            current_session = (
                self._thread_local.session_stack[-1]
                if self._thread_local.session_stack
                else self
            )
            stats = current_session.operator_stats[func_name]

            stats["calls"] += 1

            # 记录执行时间
            stats["execution_times"].append(duration)
            if len(stats["execution_times"]) > 100:
                stats["execution_times"].pop(0)

            # 记录重试信息
            stats["retry_counts"].append(retry_count)
            if len(stats["retry_counts"]) > 100:
                stats["retry_counts"].pop(0)
            stats["total_retries"] += retry_count

            if status == HopStatus.OK:
                stats["success"] += 1
            elif status == HopStatus.UNCERTAIN or status == HopStatus.LACK_OF_INFO:
                stats["uncertain"] += 1
            else:
                stats["errors"] += 1
            # 记录log相关信息
            if retry_count != 0:
                log = f"【执行Operator】: {func_name},【核验状态】：{status},【最终结果】：{result.get('final_result', '')}\n\n"
                for retry_log in result.get("retry_logs", []):
                    log += f"【执行Operator Retry:{retry_log.get('attempt','')}】: {func_name},【核验状态】：{retry_log.get('status','')},【结果】：{retry_log.get('result', '')}\n\n"
            else:
                log = f"【执行Operator】: {func_name},【核验状态】：{status},【最终结果】：{result.get('final_result', '')}"
            # 更新时间统计
            if duration < stats["min_time"]:
                stats["min_time"] = duration
            if duration > stats["max_time"]:
                stats["max_time"] = duration

            # 收集状态和日志用于函数级统计
            FunctionStatusLogCollector.collect_status_log(status, log)

    def record_function(
        self, func_name: str, duration: float, collector: List[Tuple[HopStatus, str]]
    ) -> None:
        """记录函数执行，基于算子状态集合"""
        with self._lock:
            current_session = (
                self._thread_local.session_stack[-1]
                if self._thread_local.session_stack
                else self
            )
            stats = current_session.function_stats[func_name]
            stats["calls"] += 1
            stats["execution_times"].append(duration)

            if len(stats["execution_times"]) > 100:
                stats["execution_times"].pop(0)
            if collector:
                last_status, _ = collector[-1]
                if last_status in (HopStatus.FAIL, "exception"):
                    stats["errors"] += 1
                elif last_status in (HopStatus.LACK_OF_INFO, HopStatus.UNCERTAIN):
                    stats["uncertain"] += 1
                else:
                    stats["success"] += 1

                stats["function_status"] = last_status
            for _, log in collector:
                stats["function_log"].append(log)

    def get_operator_stats(self, func_name=None):
        """获取算子统计"""
        with self._lock:
            if func_name:
                return self._format_operator_stats(
                    self.operator_stats.get(func_name, {})
                )

            return {
                name: self._format_operator_stats(stats)
                for name, stats in self.operator_stats.items()
            }

    def _format_operator_stats(self, stats):
        """格式化算子统计信息"""
        if not stats or stats["calls"] == 0:
            return {}

        times = stats["execution_times"]
        avg_time = sum(times) / len(times) if times else 0

        retry_counts = stats["retry_counts"]
        avg_retries = (
            sum(retry_counts) / len(retry_counts) if len(retry_counts) > 0 else 0
        )

        return {
            "calls": stats["calls"],
            "success_rate": stats["success"] / stats["calls"],
            "uncertain_rate": stats["uncertain"] / stats["calls"],
            "error_rate": stats["errors"] / stats["calls"],
            "avg_time": avg_time,
            "min_time": stats["min_time"],
            "max_time": stats["max_time"],
            "avg_retry_count": avg_retries,
            "total_retries": stats["total_retries"],
        }

    def get_function_stats(self, func_name=None):
        """获取函数统计"""
        with self._lock:
            if func_name:
                return self._format_function_stats(
                    self.function_stats.get(func_name, {})
                )

            return {
                name: self._format_function_stats(stats)
                for name, stats in self.function_stats.items()
            }

    def _format_function_stats(self, stats):
        """格式化函数统计信息"""
        if not stats or stats["calls"] == 0:
            return {}

        times = stats["execution_times"]
        avg_time = sum(times) / len(times) if times else 0

        total = stats["calls"]
        success_rate = stats["success"] / total if total > 0 else 0
        uncertain_rate = stats["uncertain"] / total if total > 0 else 0
        error_rate = stats["errors"] / total if total > 0 else 0

        return {
            "calls": total,
            "success_rate": success_rate,
            "uncertain_rate": uncertain_rate,
            "error_rate": error_rate,
            "avg_time": avg_time,
            "function_status": stats["function_status"],
            "function_log": stats["function_log"],
        }


# 全局统计实例
GLOBAL_STATS = ExecutionStats()

# ==============================
# 装饰器定义
# ==============================
def auto_record_status(func):
    """算子状态自动记录注解"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with ExecutionStats() as session_stats:
            session_stats = cast(ExecutionStats, session_stats)
            RetryContext.reset_retry_count()
            RetryContext.reset_retry_logs()

            start_time = time.time()
            try:
                status, result = func(*args, **kwargs)
                duration = time.time() - start_time

                # 同时记录到会话和全局统计
                session_stats.record_operator(
                    func.__name__,
                    status,
                    {
                        "final_result": result,
                        "retry_logs": RetryContext.get_retry_logs(),
                    },
                    duration,
                    RetryContext.get_retry_count(),
                )
                if status != HopStatus.OK:
                    raise ValueError(f"Operator failed: {func.__name__}", result)
                return status, result
            except Exception as e:
                duration = time.time() - start_time
                # 异常处理中同样记录
                session_stats.record_operator(
                    func.__name__,
                    HopStatus.FAIL,
                    {"error": str(e)},
                    duration,
                    RetryContext.get_retry_count(),
                )
                raise

    return wrapper


def function_monitor(func):
    """业务函数监控注解 - 收集算子、函数状态（当前会话、全局）"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with ExecutionStats() as session_stats:  # 会话级统计
            session_stats = cast(ExecutionStats, session_stats)
            FunctionStatusLogCollector.reset_collector()
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                collector = FunctionStatusLogCollector.get_collector()

                # 记录当前会话统计
                session_stats.record_function(func.__name__, duration, collector)
                # 获取当前会话的函数统计数据并返回
                current_stats = session_stats
                return result, current_stats
            except Exception as e:
                duration = time.time() - start_time
                collector = FunctionStatusLogCollector.get_collector()
                collector.append(("exception", str(e)))

                # 记录当前会话统计
                session_stats.record_function(func.__name__, duration, collector)
                raise

    return wrapper

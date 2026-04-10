"""IBI缓冲区 - 接收并存储ESP32心跳间隔数据"""
import threading
import time
from collections import deque
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import statistics


class IBIBuffer:
    """
    IBI (Inter-Beat Interval) 数据缓冲区
    
    功能：
    1. 接收单个 IBI 值（每次心跳发送一个值，单位：毫秒）
    2. 按时间窗口存储数据
    3. 提供窗口内数据的统计特征提取
    
    数据格式：
    - ESP32 每次心跳发送: "850.23" (纯数字字符串，单位ms)
    - 缓冲区存储: (timestamp, ibi_value) 元组
    """

    DEFAULT_WINDOW_SECONDS = 60

    def __init__(self, window_seconds: int = DEFAULT_WINDOW_SECONDS,
                 max_size: int = 10000):
        self.window_seconds = window_seconds
        self.max_size = max_size
        self._buffer: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._last_callback_time = 0
        self._callback_interval = 5.0
        self._data_callback = None

    def set_data_callback(self, callback):
        """设置数据就绪回调（窗口数据满时触发）"""
        self._data_callback = callback

    def set_window(self, seconds: int):
        """设置窗口时长（秒）"""
        self.window_seconds = seconds

    def add_ibi(self, ibi_value: float,
                user_id: str = "default",
                device_id: str = "esp32_001",
                timestamp: Optional[float] = None) -> Dict:
        """
        添加单个 IBI 值
        
        Args:
            ibi_value: 心跳间隔（毫秒），如 850.23
            user_id: 用户ID
            device_id: 设备ID
            timestamp: 时间戳（秒），默认当前时间
            
        Returns:
            当前窗口状态信息
        """
        if timestamp is None:
            timestamp = time.time()

        with self._lock:
            entry = {
                "timestamp": timestamp,
                "ibi": round(float(ibi_value), 2),
                "user_id": user_id,
                "device_id": device_id
            }
            self._buffer.append(entry)

            window_data = self._get_window_data_unlocked()
            status = {
                "added": True,
                "ibi_value": entry["ibi"],
                "total_in_buffer": len(self._buffer),
                "window_count": len(window_data),
                "window_seconds": self.window_seconds
            }

        current_time = time.time()
        if (self._data_callback and 
            current_time - self._last_callback_time >= self._callback_interval):
            
            if len(window_data) >= 10:
                features = self.extract_features(user_id)
                if features:
                    status["features"] = features
                    try:
                        self._data_callback(features)
                    except Exception:
                        pass
                    self._last_callback_time = current_time

        return status

    def add_ibi_from_mqtt(self, payload: bytes or str,
                          user_id: str = "default",
                          device_id: str = "esp32_001") -> Dict:
        """
        从 MQTT 消息添加 IBI 值
        
        Args:
            payload: MQTT 消息体（纯数字字符串，如 "850.23"）
            user_id: 用户ID
            device_id: 设备ID
            
        Returns:
            添加结果
        """
        try:
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8').strip()
            else:
                payload = str(payload).strip()

            ibi_value = float(payload)

            if ibi_value < 200 or ibi_value > 2000:
                return {"error": f"IBI value out of range: {ibi_value}"}

            return self.add_ibi(ibi_value, user_id, device_id)

        except ValueError:
            return {"error": f"Invalid IBI payload: {payload}"}

    def _get_window_data_unlocked(self) -> List[Dict]:
        """获取窗口内的数据（需在锁内调用）"""
        if not self._buffer:
            return []

        cutoff_time = time.time() - self.window_seconds
        return [entry for entry in self._buffer 
                if entry["timestamp"] >= cutoff_time]

    def get_window_ibi(self, user_id: Optional[str] = None) -> List[float]:
        """
        获取窗口内所有 IBI 值
        
        Args:
            user_id: 用户ID过滤，None表示全部
            
        Returns:
            IBI 值列表
        """
        with self._lock:
            window_data = self._get_window_data_unlocked()
            if user_id:
                window_data = [e for e in window_data 
                              if e.get("user_id") == user_id]
            return [e["ibi"] for e in window_data]

    def get_window_data(self, user_id: Optional[str] = None) -> List[Dict]:
        """
        获取窗口内原始数据
        
        Args:
            user_id: 用户ID过滤
            
        Returns:
            原始数据列表
        """
        with self._lock:
            window_data = self._get_window_data_unlocked()
            if user_id:
                window_data = [e for e in window_data 
                              if e.get("user_id") == user_id]
            return list(window_data)

    def extract_features(self, user_id: str = "default",
                         min_samples: int = 10) -> Optional[Dict]:
        """
        提取窗口内的 HRV 特征
        
        Args:
            user_id: 用户ID
            min_samples: 最小样本数
            
        Returns:
            特征字典或 None（样本不足时）
        """
        ibi_list = self.get_window_ibi(user_id)

        if len(ibi_list) < min_samples:
            return None

        mean_ibi = statistics.mean(ibi_list)
        heart_rate = 60000 / mean_ibi if mean_ibi > 0 else 0

        sdnn = statistics.stdev(ibi_list) if len(ibi_list) > 1 else 0

        rmssd = 0
        if len(ibi_list) >= 2:
            diffs = [ibi_list[i+1] - ibi_list[i] 
                    for i in range(len(ibi_list)-1)]
            rmssd = statistics.mean([d**2 for d in diffs]) ** 0.5

        pnn50 = 0
        if len(ibi_list) >= 2:
            diffs_abs = [abs(ibi_list[i+1] - ibi_list[i]) 
                        for i in range(len(ibi_list)-1)]
            nn50 = sum(1 for d in diffs_abs if d > 50)
            pnn50 = (nn50 / len(diffs_abs)) * 100

        window_data = self.get_window_data(user_id)
        timestamps = [e["timestamp"] for e in window_data]

        return {
            "user_id": user_id,
            "device_id": window_data[0].get("device_id", "unknown") if window_data else "unknown",
            "timestamp_start": datetime.fromtimestamp(
                min(timestamps)).isoformat() if timestamps else datetime.now().isoformat(),
            "timestamp_end": datetime.fromtimestamp(
                max(timestamps)).isoformat() if timestamps else datetime.now().isoformat(),
            "window_seconds": self.window_seconds,
            "sample_count": len(ibi_list),
            "sensors": {
                "heart_rate": round(heart_rate, 1),
                "ibi": ibi_list,
                "sdnn": round(sdnn, 2),
                "mean_ibi": round(mean_ibi, 2),
                "rmssd": round(rmssd, 2),
                "pnn50": round(pnn50, 1)
            }
        }

    def clear(self, user_id: Optional[str] = None):
        """清空缓冲区"""
        with self._lock:
            if user_id:
                self._buffer = deque(
                    [e for e in self._buffer 
                     if e.get("user_id") != user_id],
                    maxlen=self.max_size
                )
            else:
                self._buffer.clear()

    def get_stats(self) -> Dict:
        """获取缓冲区状态"""
        with self._lock:
            window_data = self._get_window_data_unlocked()
            users = set(e.get("user_id", "unknown") for e in window_data)
            
            user_stats = {}
            for uid in users:
                user_ibi = [e["ibi"] for e in window_data 
                           if e.get("user_id") == uid]
                user_stats[uid] = {
                    "count": len(user_ibi),
                    "mean_ibi": round(statistics.mean(user_ibi), 2) if user_ibi else 0
                }

            return {
                "total_in_buffer": len(self._buffer),
                "in_window": len(window_data),
                "window_seconds": self.window_seconds,
                "users": user_stats
            }


_ibi_buffer_instance: Optional[IBIBuffer] = None
_buffer_lock = threading.Lock()


def get_ibi_buffer() -> IBIBuffer:
    """获取全局 IBI 缓冲区实例（单例）"""
    global _ibi_buffer_instance
    with _buffer_lock:
        if _ibi_buffer_instance is None:
            _ibi_buffer_instance = IBIBuffer()
        return _ibi_buffer_instance


def reset_ibi_buffer():
    """重置全局 IBI 缓冲区"""
    global _ibi_buffer_instance
    with _buffer_lock:
        _ibi_buffer_instance = None

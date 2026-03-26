"""时序数据库 - 存储传感器数据"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

class TimeSeriesDB:
    def __init__(self):
        self._cache: Dict[str, List[Dict]] = {}

    def write(self, user_id: str, data_point: Dict) -> bool:
        timestamp = data_point.get("timestamp", datetime.now().isoformat())

        if user_id not in self._cache:
            self._cache[user_id] = []

        self._cache[user_id].append({
            "timestamp": timestamp,
            "data": data_point
        })

        if len(self._cache[user_id]) > 10000:
            self._cache[user_id] = self._cache[user_id][-5000:]

        return True

    def query(self, user_id: str, time_range: str = "24h") -> List[Dict]:
        if user_id not in self._cache:
            return []

        now = datetime.now()
        hours = self._parse_time_range(time_range)
        cutoff = now - timedelta(hours=hours)

        filtered = []
        for entry in self._cache[user_id]:
            try:
                entry_time = datetime.fromisoformat(entry["timestamp"])
                if entry_time >= cutoff:
                    filtered.append(entry)
            except (ValueError, TypeError):
                continue

        return filtered

    def query_range(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        if user_id not in self._cache:
            return []

        filtered = []
        for entry in self._cache[user_id]:
            try:
                entry_time = datetime.fromisoformat(entry["timestamp"])
                if start_time <= entry_time <= end_time:
                    filtered.append(entry)
            except (ValueError, TypeError):
                continue

        return filtered

    def get_latest(self, user_id: str, limit: int = 10) -> List[Dict]:
        if user_id not in self._cache:
            return []

        return self._cache[user_id][-limit:]

    def delete_old_data(self, user_id: str, days: int = 30) -> int:
        if user_id not in self._cache:
            return 0

        cutoff = datetime.now() - timedelta(days=days)
        original_len = len(self._cache[user_id])

        self._cache[user_id] = [
            entry for entry in self._cache[user_id]
            if datetime.fromisoformat(entry["timestamp"]) >= cutoff
        ]

        return original_len - len(self._cache[user_id])

    def _parse_time_range(self, time_range: str) -> int:
        time_map = {
            "1h": 1,
            "6h": 6,
            "12h": 12,
            "24h": 24,
            "7d": 168,
            "30d": 720
        }
        return time_map.get(time_range, 24)

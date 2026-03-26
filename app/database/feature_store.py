"""特征库 - 存储ML提取的高阶特征"""
from typing import Dict, Optional, List
from datetime import datetime
import json

class FeatureStore:
    def __init__(self):
        self._profiles: Dict[str, Dict] = {}

    def save_features(self, user_id: str, features: Dict) -> bool:
        if user_id not in self._profiles:
            self._profiles[user_id] = {
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
                "feature_history": [],
                "recent_features": {}
            }

        self._profiles[user_id]["feature_history"].append({
            "timestamp": datetime.now().isoformat(),
            "features": features
        })

        if len(self._profiles[user_id]["feature_history"]) > 1000:
            self._profiles[user_id]["feature_history"] = \
                self._profiles[user_id]["feature_history"][-500:]

        self._profiles[user_id]["recent_features"] = features
        self._profiles[user_id]["updated_at"] = datetime.now().isoformat()

        return True

    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        return self._profiles.get(user_id)

    def update_user_profile(self, user_id: str, profile: Dict) -> bool:
        if user_id not in self._profiles:
            self._profiles[user_id] = {
                "user_id": user_id,
                "created_at": datetime.now().isoformat()
            }

        self._profiles[user_id].update(profile)
        self._profiles[user_id]["updated_at"] = datetime.now().isoformat()

        return True

    def get_feature_trends(
        self,
        user_id: str,
        metric: str,
        days: int = 7
    ) -> List[Dict]:
        if user_id not in self._profiles:
            return []

        profile = self._profiles[user_id]
        history = profile.get("feature_history", [])

        cutoff = datetime.now().timestamp() - (days * 86400)
        recent = [
            entry for entry in history
            if datetime.fromisoformat(entry["timestamp"]).timestamp() >= cutoff
        ]

        trends = []
        for entry in recent:
            value = entry.get("features", {}).get(metric)
            if value is not None:
                trends.append({
                    "timestamp": entry["timestamp"],
                    "value": value
                })

        return trends

    def compute_aggregated_stats(self, user_id: str, days: int = 7) -> Dict:
        trends_stress = self.get_feature_trends(user_id, "stress_index", days)
        if not trends_stress:
            return {
                "avg_stress": 0,
                "max_stress": 0,
                "min_stress": 0,
                "stress_trend": 0
            }

        values = [t["value"] for t in trends_stress]
        import numpy as np
        return {
            "avg_stress": float(np.mean(values)),
            "max_stress": float(np.max(values)),
            "min_stress": float(np.min(values)),
            "stress_trend": float(values[-1] - values[0]) / len(values) if len(values) > 1 else 0
        }

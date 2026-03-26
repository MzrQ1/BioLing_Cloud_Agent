"""云端二次预处理"""
import numpy as np
from typing import List, Tuple

class Preprocessor:
    def normalize(self, data: np.ndarray, method: str = "minmax") -> np.ndarray:
        if method == "minmax":
            min_val = np.min(data)
            max_val = np.max(data)
            if max_val - min_val == 0:
                return np.zeros_like(data)
            return (data - min_val) / (max_val - min_val)
        elif method == "zscore":
            mean = np.mean(data)
            std = np.std(data)
            if std == 0:
                return np.zeros_like(data)
            return (data - mean) / std
        return data

    def interpolate_missing(self, data: np.ndarray) -> np.ndarray:
        mask = np.isnan(data)
        if not np.any(mask):
            return data

        valid_indices = np.where(~mask)[0]
        if len(valid_indices) < 2:
            return np.zeros_like(data)

        missing_indices = np.where(mask)[0]
        data[missing_indices] = np.interp(missing_indices, valid_indices, data[valid_indices])
        return data

    def create_window_slices(
        self,
        data: np.ndarray,
        window_size: int = 60,
        overlap: int = 30
    ) -> List[np.ndarray]:
        slices = []
        step = window_size - overlap
        for i in range(0, len(data) - window_size + 1, step):
            slices.append(data[i:i + window_size])
        return slices

    def resample(self, data: np.ndarray, target_length: int) -> np.ndarray:
        if len(data) == target_length:
            return data

        indices = np.linspace(0, len(data) - 1, target_length)
        return np.interp(indices, np.arange(len(data)), data)

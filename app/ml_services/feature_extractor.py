"""特征提取器 - HRV/频域/非线性特征"""
import numpy as np
from typing import Dict, List, Optional

class FeatureExtractor:
    def extract_time_domain_features(self, rr_intervals: List[float]) -> Dict[str, float]:
        if not rr_intervals or len(rr_intervals) < 2:
            return {}

        rr_arr = np.array(rr_intervals)
        diff_rr = np.diff(rr_arr)

        mean_rr = np.mean(rr_arr)
        sdnn = np.std(rr_arr)
        rmssd = np.sqrt(np.mean(diff_rr ** 2))
        nn50 = np.sum(np.abs(diff_rr) > 50)
        pnn50 = (nn50 / len(diff_rr)) * 100 if len(diff_rr) > 0 else 0

        return {
            "mean_rr": float(mean_rr),
            "sdnn": float(sdnn),
            "rmssd": float(rmssd),
            "nn50": int(nn50),
            "pnn50": float(pnn50)
        }

    def extract_frequency_domain_features(self, rr_intervals: List[float], fs: float = 4.0) -> Dict[str, float]:
        if not rr_intervals or len(rr_intervals) < 4:
            return {}

        try:
            from scipy import signal
            rr_arr = np.array(rr_intervals)
            hr = 60000 / rr_arr
            hr_interp = np.interp(
                np.arange(len(hr)),
                np.linspace(0, len(hr) - 1, num=int(len(hr) * 0.5)),
                hr
            )

            f, psd = signal.welch(hr_interp, fs=fs, nperseg=min(256, len(hr_interp)))

            lf_band = (0.04, 0.15)
            hf_band = (0.15, 0.4)

            lf_mask = (f >= lf_band[0]) & (f <= lf_band[1])
            hf_mask = (f >= hf_band[0]) & (f <= hf_band[1])

            lf_power = np.trapz(psd[lf_mask], f[lf_mask]) if np.any(lf_mask) else 0
            hf_power = np.trapz(psd[hf_mask], f[hf_mask]) if np.any(hf_mask) else 0

            lf_hf_ratio = lf_power / hf_power if hf_power > 0 else 0

            return {
                "lf_power": float(lf_power),
                "hf_power": float(hf_power),
                "lf_hf_ratio": float(lf_hf_ratio)
            }
        except ImportError:
            return {}

    def extract_nonlinear_features(self, rr_intervals: List[float]) -> Dict[str, float]:
        if not rr_intervals or len(rr_intervals) < 10:
            return {}

        try:
            import scipy.stats as stats
            from scipy.spatial.distance import pdist
            from scipy.stats import entropy

            rr_arr = np.array(rr_intervals)

            sample_entropy = self._calculate_sample_entropy(rr_arr, m=2, r=0.2)
            correlation_dimension = self._calculate_correlation_dimension(rr_arr)

            return {
                "sample_entropy": float(sample_entropy) if not np.isnan(sample_entropy) else 0.0,
                "correlation_dimension": float(correlation_dimension) if not np.isnan(correlation_dimension) else 0.0
            }
        except ImportError:
            return {}

    def _calculate_sample_entropy(self, data: np.ndarray, m: int = 2, r: float = 0.2) -> float:
        N = len(data)
        r_threshold = r * np.std(data, ddof=1)

        def _maxdist(xi, xj):
            return max([abs(ua - va) for ua, va in zip(xi, xj)])

        def _phi(m):
            patterns = np.array([data[i:i + m] for i in range(N - m)])
            count = 0
            for i in range(len(patterns)):
                for j in range(len(patterns)):
                    if i != j and _maxdist(patterns[i], patterns[j]) < r_threshold:
                        count += 1
            return count / (N - m) if N > m else 0

        phi_m = _phi(m)
        phi_m1 = _phi(m + 1)

        if phi_m == 0 or phi_m1 == 0:
            return float('nan')

        return -np.log(phi_m1 / phi_m)

    def _calculate_correlation_dimension(self, data: np.ndarray, m: int = 2) -> float:
        N = len(data)
        if N < 2 * m:
            return 0.0

        patterns = np.array([data[i:i + m] for i in range(N - m)])
        distances = pdist(patterns, metric='chebyshev')

        r_max = np.max(distances)
        epsilon_values = np.linspace(0.01 * r_max, 0.5 * r_max, 10)

        correlation_integral = []
        for epsilon in epsilon_values:
            count = np.sum(distances < epsilon)
            correlation_integral.append(count / len(distances) if len(distances) > 0 else 0)

        if len(correlation_integral) > 1 and all(c > 0 for c in correlation_integral):
            slope = (np.log10(correlation_integral[-1]) - np.log10(correlation_integral[0])) / \
                    (np.log10(epsilon_values[-1]) - np.log10(epsilon_values[0]))
            return slope
        return 0.0

    def extract_all_features(self, sensor_data: Dict) -> Dict:
        rr_intervals = sensor_data.get("rr_intervals", [])

        time_features = self.extract_time_domain_features(rr_intervals)
        freq_features = self.extract_frequency_domain_features(rr_intervals)
        nonlinear_features = self.extract_nonlinear_features(rr_intervals)

        all_features = {
            **{f"hrv_{k}": v for k, v in time_features.items()},
            **{f"freq_{k}": v for k, v in freq_features.items()},
            **{f"nonlinear_{k}": v for k, v in nonlinear_features.items()},
            "heart_rate": sensor_data.get("heart_rate", 0),
            "skin_conductance": sensor_data.get("skin_conductance", 0),
            "temperature": sensor_data.get("temperature", 0),
            "blood_oxygen": sensor_data.get("blood_oxygen", 0)
        }

        return all_features

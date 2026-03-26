"""测试ML流水线 - 特征提取和模型推理"""
import pytest
import numpy as np
from app.ml_services.feature_extractor import FeatureExtractor
from app.ml_services.inference_engine import InferenceEngine
from app.ml_services.preprocessing import Preprocessor

class TestFeatureExtractor:
    def setup_method(self):
        self.extractor = FeatureExtractor()

    def test_time_domain_features(self):
        rr_intervals = [800, 820, 810, 830, 815, 825, 840, 818]
        features = self.extractor.extract_time_domain_features(rr_intervals)

        assert "mean_rr" in features
        assert "sdnn" in features
        assert "rmssd" in features
        assert features["mean_rr"] > 0

    def test_empty_rr_intervals(self):
        features = self.extractor.extract_time_domain_features([])
        assert features == {}

    def test_frequency_domain_features(self):
        rr_intervals = [800] * 100
        features = self.extractor.extract_frequency_domain_features(rr_intervals, fs=4.0)
        assert isinstance(features, dict)

    def test_nonlinear_features(self):
        rr_intervals = [800 + np.random.randn() * 10 for _ in range(50)]
        features = self.extractor.extract_nonlinear_features(rr_intervals)
        assert isinstance(features, dict)

    def test_extract_all_features(self):
        sensor_data = {
            "rr_intervals": [800, 820, 810, 830, 815],
            "heart_rate": 75,
            "skin_conductance": 0.5,
            "temperature": 36.5,
            "blood_oxygen": 98
        }
        features = self.extractor.extract_all_features(sensor_data)

        assert "heart_rate" in features
        assert "hrv_mean_rr" in features
        assert features["heart_rate"] == 75

class TestInferenceEngine:
    def setup_method(self):
        self.engine = InferenceEngine()

    def test_rule_based_stress_predict(self):
        features = {
            "heart_rate": 90,
            "hrv_sdnn": 25,
            "hrv_rmssd": 15,
            "skin_conductance": 0.8
        }
        stress = self.engine.predict_stress(features)
        assert 0 <= stress <= 100

    def test_predict_emotion(self):
        features = {
            "heart_rate": 100,
            "hrv_sdnn": 20,
            "hrv_rmssd": 10,
            "skin_conductance": 0.9
        }
        result = self.engine.predict_emotion(features)

        assert "emotion" in result
        assert "confidence" in result
        assert "stress_index" in result
        assert "risk_level" in result

    def test_anomaly_detection(self):
        features = {
            "heart_rate": 50,
            "blood_oxygen": 85,
            "temperature": 40
        }
        result = self.engine.predict_anomaly(features)

        assert "is_anomaly" in result
        assert "anomaly_score" in result
        assert result["is_anomaly"] == True

class TestPreprocessor:
    def setup_method(self):
        self.preprocessor = Preprocessor()

    def test_normalize_minmax(self):
        data = np.array([0, 1, 2, 3, 4])
        normalized = self.preprocessor.normalize(data, method="minmax")

        assert np.min(normalized) == 0.0
        assert np.max(normalized) == 1.0

    def test_normalize_zscore(self):
        data = np.array([10, 20, 30, 40, 50])
        normalized = self.preprocessor.normalize(data, method="zscore")

        assert abs(np.mean(normalized)) < 0.01

    def test_interpolate_missing(self):
        data = np.array([1.0, np.nan, 3.0, np.nan, 5.0])
        interpolated = self.preprocessor.interpolate_missing(data)

        assert not np.any(np.isnan(interpolated))

    def test_create_window_slices(self):
        data = np.arange(100)
        slices = self.preprocessor.create_window_slices(data, window_size=20, overlap=5)

        assert len(slices) > 1
        assert len(slices[0]) == 20

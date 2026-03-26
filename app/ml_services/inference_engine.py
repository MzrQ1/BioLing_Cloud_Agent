"""推理引擎 - 封装ONNX Runtime/TorchScript"""
import numpy as np
from typing import Dict, Optional
from app.config import config

class InferenceEngine:
    def __init__(self):
        self.stress_model = None
        self.anomaly_model = None
        self._load_models()

    def _load_models(self):
        try:
            import onnxruntime as ort
            if config.STRESS_MODEL_PATH.exists():
                self.stress_model = ort.InferenceSession(str(config.STRESS_MODEL_PATH))
            if config.ANOMALY_MODEL_PATH.exists():
                self.anomaly_model = ort.InferenceSession(str(config.ANOMALY_MODEL_PATH))
        except ImportError:
            pass

    def predict_stress(self, features: Dict) -> float:
        if self.stress_model is None:
            return self._rule_based_stress_predict(features)

        try:
            import onnxruntime as ort
            feature_vector = self._prepare_feature_vector(features)
            input_name = self.stress_model.get_inputs()[0].name
            output_name = self.stress_model.get_outputs()[0].name
            result = self.stress_model.run([output_name], {input_name: [feature_vector]})
            return float(result[0][0])
        except Exception:
            return self._rule_based_stress_predict(features)

    def predict_emotion(self, features: Dict) -> Dict:
        stress_index = self.predict_stress(features)

        emotion = "calm"
        confidence = 0.5

        if stress_index > 80:
            emotion = "high_stress"
            confidence = 0.9
        elif stress_index > 60:
            emotion = "moderate_stress"
            confidence = 0.8
        elif stress_index > 40:
            emotion = "mild_stress"
            confidence = 0.7
        elif stress_index > 20:
            emotion = "relaxed"
            confidence = 0.7
        else:
            emotion = "calm"
            confidence = 0.8

        risk_level = self._stress_to_risk_level(stress_index)

        return {
            "emotion": emotion,
            "confidence": confidence,
            "stress_index": stress_index,
            "risk_level": risk_level,
            "stress_trend": self._calculate_stress_trend(features)
        }

    def predict_anomaly(self, features: Dict) -> Dict:
        if self.anomaly_model is None:
            return self._rule_based_anomaly_predict(features)

        try:
            feature_vector = self._prepare_feature_vector(features)
            input_name = self.anomaly_model.get_inputs()[0].name
            output_name = self.anomaly_model.get_outputs()[0].name
            result = self.anomaly_model.run([output_name], {input_name: [feature_vector]})
            return {
                "is_anomaly": bool(result[0][0] > 0.5),
                "anomaly_score": float(result[0][0])
            }
        except Exception:
            return self._rule_based_anomaly_predict(features)

    def _prepare_feature_vector(self, features: Dict) -> list:
        feature_order = [
            "hrv_sdnn", "hrv_rmssd", "hrv_pnn50",
            "freq_lf_power", "freq_hf_power", "freq_lf_hf_ratio",
            "nonlinear_sample_entropy", "nonlinear_correlation_dimension",
            "heart_rate", "skin_conductance", "temperature", "blood_oxygen"
        ]

        vector = []
        for key in feature_order:
            value = features.get(key, 0.0)
            if isinstance(value, (int, float)) and not np.isnan(value):
                vector.append(float(value))
            else:
                vector.append(0.0)

        return vector

    def _rule_based_stress_predict(self, features: Dict) -> float:
        hr = features.get("heart_rate", 70)
        hrv_sdnn = features.get("hrv_sdnn", 40)
        hrv_rmssd = features.get("hrv_rmssd", 20)
        sc = features.get("skin_conductance", 0.5)

        stress = 50.0
        if hr > 100:
            stress += (hr - 100) * 0.8
        if hr < 60:
            stress += (60 - hr) * 0.5

        if hrv_sdnn < 30:
            stress += (30 - hrv_sdnn) * 1.5
        if hrv_rmssd < 15:
            stress += (15 - hrv_rmssd) * 1.2

        stress += sc * 20

        return max(0.0, min(100.0, stress))

    def _rule_based_anomaly_predict(self, features: Dict) -> Dict:
        hr = features.get("heart_rate", 70)
        spo2 = features.get("blood_oxygen", 98)
        temp = features.get("temperature", 36.5)

        is_anomaly = False
        anomaly_score = 0.0

        if hr < 40 or hr > 180:
            is_anomaly = True
            anomaly_score = 0.9
        elif spo2 < 90:
            is_anomaly = True
            anomaly_score = 0.8
        elif temp < 35 or temp > 39:
            is_anomaly = True
            anomaly_score = 0.7

        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": anomaly_score
        }

    def _stress_to_risk_level(self, stress_index: float) -> str:
        if stress_index > 75:
            return "critical"
        elif stress_index > 60:
            return "high"
        elif stress_index > 40:
            return "moderate"
        else:
            return "low"

    def _calculate_stress_trend(self, features: Dict) -> float:
        current_stress = features.get("current_stress", 50)
        previous_stress = features.get("previous_stress", 50)

        if previous_stress == 0:
            return 0.5

        trend = (current_stress - previous_stress) / previous_stress
        return max(0.0, min(1.0, (trend + 1) / 2))

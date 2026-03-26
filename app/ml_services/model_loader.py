"""模型加载器"""
import os
from pathlib import Path
from typing import Optional

class ModelLoader:
    def __init__(self, model_dir: Optional[str] = None):
        if model_dir:
            self.model_dir = Path(model_dir)
        else:
            from app.config import config
            self.model_dir = config.MODEL_CACHE_DIR

    def load_onnx_model(self, model_name: str):
        model_path = self.model_dir / model_name
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        try:
            import onnxruntime as ort
            session = ort.InferenceSession(str(model_path))
            return session
        except ImportError:
            return None

    def load_torch_model(self, model_name: str):
        model_path = self.model_dir / model_name
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        try:
            import torch
            model = torch.jit.load(str(model_path))
            model.eval()
            return model
        except ImportError:
            return None

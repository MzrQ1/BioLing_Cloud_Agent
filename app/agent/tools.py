"""工具封装 - LLM调用和辅助函数"""
import os
import json
from typing import Optional, Dict, Any, List
from app.config import config, LLMConfig

class LLMCaller:
    """大模型调用器 - 支持多种Provider"""

    @staticmethod
    def call(prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """统一调用接口"""
        provider = LLMConfig.PROVIDER

        if provider == "openai":
            return LLMCaller._call_openai(prompt, model, **kwargs)
        elif provider == "dashscope":
            return LLMCaller._call_dashscope(prompt, model, **kwargs)
        elif provider == "anthropic":
            return LLMCaller._call_anthropic(prompt, model, **kwargs)
        elif provider == "ollama":
            return LLMCaller._call_ollama(prompt, model, **kwargs)
        elif provider == "vllm":
            return LLMCaller._call_vllm(prompt, model, **kwargs)
        else:
            return LLMCaller._call_dashscope(prompt, model, **kwargs)

    @staticmethod
    def _call_dashscope(prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """阿里云DashScope千问API接口"""
        model = model or LLMConfig.DIALOG_MODEL
        api_key = LLMConfig.DIALOG_API_KEY
        api_base = LLMConfig.DIALOG_API_BASE

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=api_base)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", LLMConfig.TEMPERATURE),
                max_tokens=kwargs.get("max_tokens", LLMConfig.MAX_TOKENS)
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"LLM调用失败: {str(e)}"

    @staticmethod
    def _call_openai(prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """OpenAI兼容接口"""
        model = model or LLMConfig.DIALOG_MODEL
        api_key = LLMConfig.DIALOG_API_KEY
        api_base = LLMConfig.DIALOG_API_BASE

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=api_base)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", LLMConfig.TEMPERATURE),
                max_tokens=kwargs.get("max_tokens", LLMConfig.MAX_TOKENS)
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"LLM调用失败: {str(e)}"

    @staticmethod
    def _call_anthropic(prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """Anthropic Claude接口"""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
            response = client.messages.create(
                model=model or "claude-3-sonnet-20240229",
                max_tokens=kwargs.get("max_tokens", LLMConfig.MAX_TOKENS),
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"LLM调用失败: {str(e)}"

    @staticmethod
    def _call_ollama(prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """Ollama本地模型接口"""
        import urllib.request
        import urllib.error

        model = model or "llama3"
        api_base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{api_base}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("response", "")
        except Exception as e:
            return f"LLM调用失败: {str(e)}"

    @staticmethod
    def _call_vllm(prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """vLLM接口"""
        return LLMCaller._call_openai(prompt, model, **kwargs)

class EmbeddingCaller:
    """Embedding模型调用器"""

    @staticmethod
    def embed(texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """获取文本的embedding向量"""
        provider = LLMConfig.EMBEDDING_PROVIDER

        if provider == "openai":
            return EmbeddingCaller._embed_openai(texts, model)
        elif provider == "ollama":
            return EmbeddingCaller._embed_ollama(texts, model)
        else:
            return EmbeddingCaller._embed_ollama(texts, model)

    @staticmethod
    def _embed_openai(texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """OpenAI Embedding接口"""
        model = model or LLMConfig.EMBEDDING_MODEL
        api_key = LLMConfig.EMBEDDING_API_KEY
        api_base = LLMConfig.EMBEDDING_API_BASE

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=api_base)
            response = client.embeddings.create(
                model=model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            return [[0.0] * 1536]

    @staticmethod
    def _embed_ollama(texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Ollama Embedding接口"""
        import urllib.request
        import urllib.error

        model = model or LLMConfig.EMBEDDING_MODEL
        api_base = LLMConfig.EMBEDDING_API_BASE

        embeddings = []
        for text in texts:
            payload = {"model": model, "prompt": text}
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    f"{api_base}/api/embeddings",
                    data=data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    embeddings.append(result.get("embedding", []))
            except Exception:
                embeddings.append([0.0] * 768)

        return embeddings

def llm_call(prompt: str, model: Optional[str] = None) -> str:
    """调用LLM生成文本（兼容旧接口）"""
    return LLMCaller.call(prompt, model)

def format_sensor_data(raw_data: dict) -> dict:
    """格式化传感器数据"""
    processed = {
        "heart_rate": raw_data.get("hr", 0),
        "heart_rate_variability": raw_data.get("hrv", 0),
        "skin_conductance": raw_data.get("sc", 0),
        "temperature": raw_data.get("temp", 0),
        "blood_oxygen": raw_data.get("spo2", 0),
        "timestamp": raw_data.get("timestamp", "")
    }
    return processed

def calculate_hrv_features(rr_intervals: list) -> dict:
    """计算HRV时域特征"""
    if not rr_intervals or len(rr_intervals) < 2:
        return {}

    import numpy as np
    rr_arr = np.array(rr_intervals)

    mean_rr = np.mean(rr_arr)
    sdnn = np.std(rr_arr)
    rmssd = np.sqrt(np.mean(np.diff(rr_arr) ** 2))

    return {
        "mean_rr": float(mean_rr),
        "sdnn": float(sdnn),
        "rmssd": float(rmssd)
    }

def stress_index_from_hrv(hrv_features: dict) -> float:
    """基于HRV特征计算压力指数"""
    sdnn = hrv_features.get("sdnn", 50)
    rmssd = hrv_features.get("rmssd", 20)

    stress = 100 - (sdnn / 2 + rmssd / 4)
    stress = max(0, min(100, stress))
    return float(stress)

def should_trigger_emergency(risk_level: str) -> bool:
    """判断是否触发紧急干预"""
    return risk_level in ["critical", "high"]

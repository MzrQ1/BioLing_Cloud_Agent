"""HTTP API路由"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
import uuid

router = APIRouter()

class ESP32SensorData(BaseModel):
    user_id: str
    device_id: Optional[str] = "esp32_001"
    timestamp: str
    ibi: List[float]
    sdnn: float

class ReportQuery(BaseModel):
    user_id: str
    time_range: Optional[str] = "24h"

class UserFeedbackRequest(BaseModel):
    report_id: str
    feedback: str

class WebLoginRequest(BaseModel):
    username: str
    password: str

class WebChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str

_agent_instance = None

def set_agent_instance(agent):
    global _agent_instance
    _agent_instance = agent

def process_esp32_data(data: ESP32SensorData) -> dict:
    ibi_list = data.ibi
    sdnn = data.sdnn

    mean_ibi = sum(ibi_list) / len(ibi_list) if ibi_list else 0
    heart_rate = 60000 / mean_ibi if mean_ibi > 0 else 0

    rmssd = 0
    if len(ibi_list) >= 2:
        diffs = [ibi_list[i+1] - ibi_list[i] for i in range(len(ibi_list)-1)]
        rmssd = (sum(d*d for d in diffs) / len(diffs)) ** 0.5

    return {
        "user_id": data.user_id,
        "device_id": data.device_id,
        "timestamp": data.timestamp,
        "sensors": {
            "heart_rate": round(heart_rate, 1),
            "ibi": ibi_list,
            "sdnn": sdnn,
            "mean_ibi": round(mean_ibi, 1),
            "rmssd": round(rmssd, 1)
        }
    }

@router.post("/sensor/esp32")
async def receive_esp32_data(data: ESP32SensorData, background_tasks: BackgroundTasks):
    sensor_payload = process_esp32_data(data)

    if _agent_instance:
        from app.agent.state import HealthState

        state = HealthState(
            user_id=data.user_id,
            session_id=str(uuid.uuid4()),
            raw_sensor_data=sensor_payload,
            processed_features=sensor_payload["sensors"],
            short_term_memory=[],
            ml_features=None,
            risk_level="low",
            intervention_type="none",
            next_node="short_term_memory",
            should_continue=False
        )

        background_tasks.add_task(_agent_instance.ainvoke, state)

    return {
        "status": "received",
        "timestamp": data.timestamp,
        "message": "数据已接收，正在处理..."
    }

@router.post("/sensor/data")
async def receive_sensor_data(data: ESP32SensorData, background_tasks: BackgroundTasks):
    return await receive_esp32_data(data, background_tasks)

@router.post("/report/query")
async def query_report(query: ReportQuery):
    from app.database import TimeSeriesDB, FeatureStore

    ts_db = TimeSeriesDB()
    feature_store = FeatureStore()

    historical = ts_db.query(query.user_id, query.time_range)
    profile = feature_store.get_user_profile(query.user_id)

    return {
        "user_id": query.user_id,
        "time_range": query.time_range,
        "data_points": len(historical),
        "profile": profile,
        "generated_at": datetime.now().isoformat()
    }

@router.get("/report/{user_id}")
async def get_latest_report(user_id: str):
    from app.database import FeatureStore

    feature_store = FeatureStore()
    profile = feature_store.get_user_profile(user_id)

    if not profile:
        raise HTTPException(status_code=404, detail="未找到用户报告")

    return {
        "user_id": user_id,
        "report": profile.get("latest_report"),
        "generated_at": profile.get("updated_at"),
        "risk_level": profile.get("recent_features", {}).get("risk_level", "unknown")
    }

@router.post("/web/login")
async def web_login(credentials: WebLoginRequest):
    return {
        "status": "success",
        "user_id": credentials.username,
        "session_id": str(uuid.uuid4()),
        "message": "登录成功，欢迎回来！"
    }

@router.post("/web/chat")
async def web_chat(chat_request: WebChatRequest):
    if _agent_instance:
        from app.agent.state import HealthState

        state = HealthState(
            user_id=chat_request.user_id,
            session_id=chat_request.session_id,
            raw_sensor_data=None,
            processed_features=None,
            short_term_memory=[],
            ml_features=None,
            risk_level="low",
            intervention_type="none",
            next_node="interaction_reflection",
            should_continue=False,
            user_input=chat_request.message
        )

        result = _agent_instance.invoke(state)
        return {
            "status": "success",
            "response": result.get("reflection_result", "感谢您的反馈！"),
            "suggestion": result.get("suggestion")
        }

    return {
        "status": "success",
        "response": "感谢您的反馈！"
    }

@router.get("/web/report/{user_id}")
async def get_web_report(user_id: str):
    from app.database import FeatureStore

    feature_store = FeatureStore()
    profile = feature_store.get_user_profile(user_id)

    if not profile:
        return {
            "user_id": user_id,
            "report": "暂无健康报告，请稍后再试或检查设备连接。"
        }

    recent_features = profile.get("recent_features", {})
    ml_features = profile.get("ml_features", {})

    report = f"""📊 健康概览

整体状态：{ml_features.get('emotion', '未知')} (压力指数: {ml_features.get('stress_index', 0)}/100)

近期表现：
- 心率: {recent_features.get('heart_rate', 0)} bpm
- 心率变异性(SDNN): {recent_features.get('sdnn', 0)} ms
- 压力等级: {ml_features.get('risk_level', 'unknown').upper()}

建议：{profile.get('latest_suggestion', '保持良好的生活习惯，定期监测健康数据。')}
"""

    return {
        "user_id": user_id,
        "report": report,
        "risk_level": ml_features.get("risk_level", "unknown")
    }

@router.post("/feedback")
async def submit_feedback(feedback: UserFeedbackRequest):
    return {
        "status": "success",
        "message": "反馈已收到，感谢您的参与！",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "biolid-cloud-agent",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/device_command/{user_id}")
async def get_pending_commands(user_id: str):
    return {
        "user_id": user_id,
        "commands": []
    }

"""HTTP API路由 - 增强版"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
import uuid
import os
import json

router = APIRouter()

AGENT_INSTANCE = None
CHAT_AGENT_INSTANCE = None

def set_agent_instance(agent):
    global AGENT_INSTANCE
    AGENT_INSTANCE = agent

def set_chat_agent_instance(agent):
    global CHAT_AGENT_INSTANCE
    CHAT_AGENT_INSTANCE = agent


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


class WebRegisterRequest(BaseModel):
    username: str
    password: str
    nickname: Optional[str] = None


class WebChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatHistoryQuery(BaseModel):
    user_id: str
    limit: int = 50
    offset: int = 0


def get_current_user(request: Request) -> Optional[Dict]:
    """从请求中获取当前用户"""
    session_id = request.headers.get("X-Session-ID") or request.cookies.get("session_id")
    
    if not session_id:
        return None
    
    from app.interfaces.auth import get_auth
    auth = get_auth()
    return auth.verify_session(session_id)


def require_auth(request: Request) -> Dict:
    """需要认证的接口"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


@router.post("/auth/register", response_model=Dict)
async def register(req: WebRegisterRequest):
    from app.interfaces.auth import get_auth
    auth = get_auth()
    result = auth.register(req.username, req.password, req.nickname)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/auth/login", response_model=Dict)
async def login(req: WebLoginRequest):
    from app.interfaces.auth import get_auth
    auth = get_auth()
    result = auth.login(req.username, req.password)
    
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])
    
    response = JSONResponse(content=result)
    response.set_cookie(
        key="session_id",
        value=result["session_id"],
        httponly=True,
        max_age=7 * 24 * 3600
    )
    return response


@router.post("/auth/logout", response_model=Dict)
async def logout(request: Request):
    session_id = request.cookies.get("session_id") or ""
    from app.interfaces.auth import get_auth
    auth = get_auth()
    auth.logout(session_id)
    
    response = JSONResponse(content={"success": True, "message": "已登出"})
    response.delete_cookie("session_id")
    return response


@router.get("/auth/me", response_model=Dict)
async def get_me(user: Dict = Depends(require_auth)):
    from app.interfaces.auth import get_auth
    auth = get_auth()
    user_info = auth.get_user_info(user["user_id"])
    return user_info or {"error": "用户不存在"}


@router.post("/sensor/esp32", response_model=Dict)
async def receive_esp32_data(data: ESP32SensorData):
    sensor_payload = _process_esp32_data(data)

    if AGENT_INSTANCE:
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

        try:
            await AGENT_INSTANCE.ainvoke(state)
        except Exception as e:
            pass

    return {
        "status": "received",
        "timestamp": data.timestamp,
        "message": "数据已接收，正在处理..."
    }


@router.post("/sensor/data", response_model=Dict)
async def receive_sensor_data(data: ESP32SensorData):
    return await receive_esp32_data(data)


@router.post("/web/chat", response_model=Dict)
async def web_chat(chat_req: WebChatRequest, request: Request):
    user = get_current_user(request)
    user_id = user["user_id"] if user else "guest"
    
    conversation_history = []
    
    from app.database.conversation_store import ConversationStore
    conv_store = ConversationStore()
    history = conv_store.get_recent_conversations(
        user_id=user_id,
        limit=10
    )
    
    for msg in history:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        conversation_history.append({"role": role, "content": content})
    
    conversation_history.append({"role": "user", "content": chat_req.message})
    
    response_text = ""
    suggestion = None
    
    if CHAT_AGENT_INSTANCE:
        from app.agent.state import HealthState
        
        state = HealthState(
            user_id=user_id,
            session_id=chat_req.session_id or str(uuid.uuid4()),
            raw_sensor_data=None,
            processed_features=None,
            short_term_memory=conversation_history,
            ml_features=None,
            risk_level="low",
            intervention_type="none",
            next_node="quick_check",
            should_continue=False,
            user_input=chat_req.message
        )

        try:
            result = CHAT_AGENT_INSTANCE.invoke(state)
            if result is None:
                response_text = "抱歉，系统暂时无法处理您的请求，请稍后重试。"
                suggestion = None
            else:
                response_text = result.get("reflection_result") or result.get("suggestion") or ""
                suggestion = result.get("suggestion")
        except Exception as e:
            response_text = f"抱歉，处理您的消息时出现了问题：{str(e)}"
            
            conv_store.save_conversation(
                user_id=user_id,
                role="user",
                content=chat_req.message,
                context={"emotion_state": "neutral"}
            )
            
            conv_store.save_conversation(
                user_id=user_id,
                role="assistant",
                content=response_text,
                context={"emotion_state": "neutral"}
            )
    else:
        from app.agent.tools import llm_call
        response_text = llm_call(f"用户问题：{chat_req.message}\n\n请作为健康管家回答。")

        conv_store.save_conversation(
            user_id=user_id,
            role="user",
            content=chat_req.message,
            context={"emotion_state": "neutral"}
        )
        
        conv_store.save_conversation(
            user_id=user_id,
            role="assistant",
            content=response_text,
            context={"emotion_state": "neutral"}
        )
    
    return {
        "status": "success",
        "response": response_text,
        "suggestion": suggestion,
        "timestamp": datetime.now().isoformat()
    }


async def generate_chat_stream(user_id: str, prompt: str, session_id: str):
    """
    生成聊天流式响应（生成器）

    根据问题复杂度自动选择小模型或大模型
    """
    from app.agent.model_router import should_use_large_model

    model_type, route_reason = should_use_large_model(
        user_input=prompt,
        ml_features=None,
        conversation_turns=0
    )

    print(f"[流式聊天] 类型: {model_type} | 原因: {route_reason} | 输入: {prompt[:30]}...")

    if model_type == "small":
        from app.agent.tools import llm_call_simple_stream
        generator = llm_call_simple_stream(prompt)
    else:
        from app.agent.tools import llm_call_stream
        generator = llm_call_stream(prompt)

    full_response = ""

    for chunk in generator:
        full_response += chunk
        yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

    from app.database.conversation_store import ConversationStore
    conv_store = ConversationStore()
    conv_store.save_conversation(
        user_id=user_id,
        role="user",
        content=prompt,
        session_id=session_id,
        context={"emotion_state": "neutral", "model_type": model_type}
    )
    conv_store.save_conversation(
        user_id=user_id,
        role="assistant",
        content=full_response,
        session_id=session_id,
        context={"emotion_state": "neutral", "model_type": model_type}
    )

    yield f"data: {json.dumps({'content': '', 'done': True, 'model_type': model_type})}\n\n"


@router.post("/web/chat/stream")
async def chat_stream(chat_req: WebChatRequest, request: Request):
    """
    流式聊天接口 - 支持流式输出

    前端可以通过 EventSource 或 fetch API 接收流式响应
    实现逐字显示效果
    """
    user = get_current_user(request)
    user_id = user["user_id"] if user else "guest"
    session_id = chat_req.session_id or str(uuid.uuid4())

    return StreamingResponse(
        generate_chat_stream(user_id, chat_req.message, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/web/chat/history", response_model=Dict)
async def get_chat_history(
    limit: int = 50, 
    offset: int = 0,
    user: Dict = Depends(require_auth)
):
    from app.database.conversation_store import ConversationStore
    
    conv_store = ConversationStore()
    history = conv_store.get_recent_conversations(
        user_id=user["user_id"],
        limit=limit,
        offset=offset
    )
    
    total = conv_store.get_conversation_count(user["user_id"])
    
    return {
        "user_id": user["user_id"],
        "history": history,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/web/report/{user_id}", response_model=Dict)
async def get_web_report(user_id: str, request: Request):
    user = get_current_user(request)
    
    if user and user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权查看其他用户数据")
    
    from app.database import FeatureStore, TimeSeriesDB, ConversationStore
    
    feature_store = FeatureStore()
    ts_db = TimeSeriesDB()
    conv_store = ConversationStore()
    
    profile = feature_store.get_user_profile(user_id)
    
    recent_data = ts_db.query(user_id, "24h")
    recent_conv = conv_store.get_recent_conversations(
        user_id=user_id, 
        limit=20
    )
    
    memory_stats = conv_store.get_memory_summary(user_id)
    
    if not profile or not profile.get("recent_features"):
        return {
            "user_id": user_id,
            "report": None,
            "message": "暂无健康数据，请连接设备进行测量。",
            "has_data": False
        }
    
    recent_features = profile.get("recent_features", {})
    ml_features = profile.get("ml_features", {})
    
    stress_trend = "stable"
    if len(recent_data) >= 2:
        first_half = [d.get("stress_index", 50) for d in recent_data[:len(recent_data)//2]]
        second_half = [d.get("stress_index", 50) for d in recent_data[len(recent_data)//2:]]
        
        if first_half and second_half:
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            diff = avg_second - avg_first
            
            if diff > 10:
                stress_trend = "increasing"
            elif diff < -10:
                stress_trend = "decreasing"
    
    risk_level = recent_features.get("risk_level", "unknown").upper()
    risk_colors = {
        "LOW": "#22c55e",
        "MODERATE": "#f59e0b", 
        "HIGH": "#ef4444",
        "CRITICAL": "#dc2626"
    }
    
    report = {
        "user_id": user_id,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "overall_status": ml_features.get("emotion", "未知"),
            "stress_level": recent_features.get("stress_index", 0),
            "risk_level": risk_level,
            "risk_color": risk_colors.get(risk_level, "#6b7280"),
            "stress_trend": stress_trend
        },
        "vitals": {
            "heart_rate": {
                "value": recent_features.get("heart_rate", 0),
                "unit": "bpm",
                "status": "normal" if 60 <= (recent_features.get("heart_rate") or 0) <= 100 else "abnormal"
            },
            "sdnn": {
                "value": recent_features.get("sdnn", 0),
                "unit": "ms",
                "status": "normal" if (recent_features.get("sdnn") or 0) >= 20 else "low"
            },
            "rmssd": {
                "value": recent_features.get("rmssd", 0),
                "unit": "ms"
            }
        },
        "statistics": {
            "total_sessions": profile.get("total_sessions", 0),
            "high_stress_events": profile.get("high_stress_events", 0),
            "data_points_24h": len(recent_data),
            "memory_count": memory_stats.get("total_conversations", 0)
        },
        "suggestion": profile.get("latest_suggestion", "保持良好的生活习惯"),
        "recent_conversations": [
            {"role": c.get("role"), "content": c.get("content", "")[:100]}
            for c in recent_conv[-5:]
        ] if recent_conv else [],
        "has_data": True
    }
    
    return report


@router.get("/web/data/physiological/{user_id}", response_model=Dict)
async def get_physiological_data(
    user_id: str, 
    time_range: str = "24h",
    user: Dict = Depends(require_auth)
):
    if user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权访问")
    
    from app.database import TimeSeriesDB
    
    ts_db = TimeSeriesDB()
    data = ts_db.query(user_id, time_range)
    
    timestamps = []
    heart_rates = []
    sdnn_values = []
    stress_indices = []
    
    for d in data:
        timestamps.append(d.get("timestamp", ""))
        heart_rates.append(d.get("heart_rate", 0))
        sdnn_values.append(d.get("sdnn", 0))
        stress_indices.append(d.get("stress_index", 50))
    
    return {
        "user_id": user_id,
        "time_range": time_range,
        "data_points": len(data),
        "timestamps": timestamps,
        "series": {
            "heart_rate": heart_rates,
            "sdnn": sdnn_values,
            "stress_index": stress_indices
        },
        "statistics": {
            "avg_hr": round(sum(heart_rates)/len(heart_rates), 1) if heart_rates else 0,
            "avg_sdnn": round(sum(sdnn_values)/len(sdnn_values), 2) if sdnn_values else 0,
            "avg_stress": round(sum(stress_indices)/len(stress_indices), 1) if stress_indices else 0,
            "max_hr": max(heart_rates) if heart_rates else 0,
            "min_hr": min(heart_rates) if heart_rates else 0
        }
    }


@router.get("/web/memory/{user_id}", response_model=Dict)
async def get_memory_data(
    user_id: str,
    user: Dict = Depends(require_auth)
):
    if user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权访问")
    
    from app.database.conversation_store import ConversationStore
    
    conv_store = ConversationStore()
    
    memories = conv_store.get_recent_conversations(user_id, limit=100)
    stats = conv_store.get_memory_summary(user_id)
    
    scored_memories = sorted(
        memories, 
        key=lambda x: x.get("memory_score", 0), 
        reverse=True
    )[:50]
    
    return {
        "user_id": user_id,
        "stats": stats,
        "memories": scored_memories
    }


@router.get("/report/{user_id}", response_model=Dict)
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


@router.post("/report/query", response_model=Dict)
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


@router.post("/feedback", response_model=Dict)
async def submit_feedback(feedback: UserFeedbackRequest):
    return {
        "status": "success",
        "message": "反馈已收到，感谢您的参与！",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/health", response_model=Dict)
async def health_check():
    return {
        "status": "healthy",
        "service": "biolid-cloud-agent",
        "version": "v0.8.0",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/device_command/{user_id}", response_model=Dict)
async def get_pending_commands(user_id: str):
    return {
        "user_id": user_id,
        "commands": []
    }


@router.get("/", response_class=HTMLResponse)
async def serve_index():
    static_dir = os.path.join(os.path.dirname(__file__), '..', 'static')
    index_path = os.path.join(static_dir, 'index.html')
    
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html><head><title>BioLid Cloud Agent</title></head>
    <body>
        <h1>🏥 BioLid Cloud Agent</h1>
        <p>服务运行正常</p>
        <p><a href="/docs">API 文档</a></p>
    </body></html>
    """)


def _process_esp32_data(data: ESP32SensorData) -> dict:
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

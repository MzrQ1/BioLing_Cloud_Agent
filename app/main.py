"""FastAPI启动入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import logging

from app.config import config
from app.interfaces.api_routes import router, set_agent_instance, set_chat_agent_instance
from app.agent.graph import create_unified_health_agent_graph, create_chat_graph
from app.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_agent_graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent_graph
    logger.info("正在初始化BioLing Cloud Agent...")

    try:
        logger.info("正在初始化SQLite数据库...")
        init_db()
        logger.info("SQLite数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")

    try:
        _agent_graph = create_unified_health_agent_graph()
        set_agent_instance(_agent_graph)
        logger.info("统一健康智能体初始化完成（兼容有/无传感器数据）")
    except Exception as e:
        logger.error(f"统一健康智能体初始化失败: {e}")

    try:
        _chat_graph = create_chat_graph()
        set_chat_agent_instance(_chat_graph)
        logger.info("轻量对话智能体初始化完成")
    except Exception as e:
        logger.error(f"轻量对话智能体初始化失败: {e}")

    logger.info("BioLing Cloud Agent启动成功")
    yield

    logger.info("正在关闭BioLing Cloud Agent...")

app = FastAPI(
    title="BioLing Cloud Agent",
    description="端云协同健康智能体 - LangGraph",
    version="0.8.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

static_dir = os.path.join(os.path.dirname(__file__), '..', 'static')
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    static_index = os.path.join(static_dir, 'index.html')
    if os.path.exists(static_index):
        from fastapi.responses import FileResponse
        return FileResponse(static_index)
    
    return {
        "service": "BioLing Cloud Agent",
        "version": "0.8.0",
        "status": "running",
        "description": "端云协同健康智能体"
    }

if __name__ == "__main__":
    import uvicorn
    from app.config import config
    uvicorn.run(app, host=config.SERVER.HOST, port=config.SERVER.PORT)

"""FastAPI启动入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import config
from app.interfaces.api_routes import router, set_agent_instance
from app.agent.graph import create_health_agent_graph
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
        _agent_graph = create_health_agent_graph()
        set_agent_instance(_agent_graph)
        logger.info("LangGraph健康智能体初始化完成")
    except Exception as e:
        logger.error(f"智能体初始化失败: {e}")

    logger.info("BioLing Cloud Agent启动成功")
    yield

    logger.info("正在关闭BioLing Cloud Agent...")

app = FastAPI(
    title="BioLing Cloud Agent",
    description="端云协同健康智能体 - LangGraph",
    version="0.1.0",
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

@app.get("/")
async def root():
    return {
        "service": "BioLing Cloud Agent",
        "version": "0.1.0",
        "status": "running",
        "description": "端云协同健康智能体"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

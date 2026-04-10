@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ========================================
echo   BioLid Cloud Agent - 本地测试启动
echo ========================================
echo.

if "%1"=="" goto help
if "%1"=="init" goto init
if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="status" goto status
if "%1"=="test" goto test
goto help

:init
echo [1/4] 创建必要目录...
if not exist "data\db" mkdir data\db
if not exist "data\logs" mkdir data\logs
if not exist "data\mosquitto\config" mkdir data\mosquitto\config
if not exist "data\mosquitto\data" mkdir data\mosquitto\data
if not exist "data\mosquitto\log" mkdir data\mosquitto\log
if not exist "docs" mkdir docs

echo [2/4] 创建 Mosquitto 配置文件...
(
echo listener 1883
echo allow_anonymous true
echo max_connections -1
) > data\mosquitto\config\mosquitto.conf

echo [3/4] 检查 .env 文件...
if not exist ".env" (
    if exist ".env.local" (
        copy .env.local .env >nul
        echo 已从 .env.local 复制配置到 .env
    ) else if exist ".env.example" (
        copy .env.example .env >nul
        echo 已从 .env.example 复制配置到 .env
    )
    echo 请编辑 .env 文件，填入你的 DASHSCOPE_API_KEY
)

echo [4/4] 检查 Python 虚拟环境...
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
)

echo.
echo 初始化完成！
echo 下一步：
echo   1. 编辑 .env 文件，填入 DASHSCOPE_API_KEY
echo   2. 运行 start.bat start 启动服务
goto end

:start
echo 启动服务...

echo [1/3] 启动 MQTT Broker (Docker)...
docker-compose -f docker-compose.local.yml up -d

echo [2/3] 检查 Ollama 服务...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo 警告: Ollama 服务未运行，请先启动 Ollama
    echo 运行命令: ollama serve
    echo 然后下载模型: ollama pull nomic-embed-text
)

echo [3/3] 启动应用服务...
call venv\Scripts\activate.bat
pip install -r requirements.txt -q
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
goto end

:stop
echo 停止服务...
docker-compose -f docker-compose.local.yml down
echo 服务已停止
goto end

:status
echo 服务状态:
echo.
echo [MQTT Broker]
docker-compose -f docker-compose.local.yml ps

echo.
echo [Ollama]
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo 状态: 未运行
) else (
    echo 状态: 运行中
    ollama list
)

echo.
echo [应用服务]
curl -s http://localhost:8001/health >nul 2>&1
if errorlevel 1 (
    echo 状态: 未运行
) else (
    echo 状态: 运行中 - http://localhost:8001
)
goto end

:test
echo 测试 API...
call venv\Scripts\activate.bat
python -c "from app.main import app; print('应用加载成功')"
curl -s http://localhost:8001/health
echo.
goto end

:help
echo 用法: start.bat [命令]
echo.
echo 命令:
echo   init    - 初始化本地测试环境
echo   start   - 启动所有服务
echo   stop    - 停止所有服务
echo   status  - 查看服务状态
echo   test    - 测试应用是否正常
echo.
echo 示例:
echo   start.bat init    # 首次使用，初始化环境
echo   start.bat start   # 启动服务
goto end

:end
endlocal

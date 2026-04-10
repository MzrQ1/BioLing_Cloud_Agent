#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

create_directories() {
    log_info "创建必要目录..."
    mkdir -p data/db
    mkdir -p data/logs
    mkdir -p docs
    mkdir -p logs
}

check_python() {
    log_info "检查Python环境..."
    
    if [ ! -d "venv" ]; then
        log_warn "虚拟环境不存在，正在创建..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    PYTHON_VERSION=$(python --version 2>&1 | grep -oP '\d+\.\d+')
    log_info "Python版本: $(python --version)"
    
    if [[ ! "$PYTHON_VERSION" =~ ^3\.(10|11) ]]; then
        log_warn "推荐使用Python 3.10或3.11，当前版本: $PYTHON_VERSION"
    fi
}

install_dependencies() {
    log_info "安装依赖..."
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
}

check_env_file() {
    log_info "检查配置文件..."
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_warn "已从.env.example创建.env文件，请编辑配置"
        else
            log_error ".env和.env.example都不存在"
            exit 1
        fi
    fi
    
    if grep -q "your-dashscope-api-key-here" .env; then
        log_warn "请先配置DASHSCOPE_API_KEY"
    fi
}

check_ollama() {
    log_info "检查Ollama服务..."
    
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_info "Ollama服务运行中"
        
        if curl -s http://localhost:11434/api/tags | grep -q "nomic-embed-text"; then
            log_info "Embedding模型已安装"
        else
            log_warn "正在下载nomic-embed-text模型..."
            ollama pull nomic-embed-text
        fi
    else
        log_warn "Ollama服务未运行，Embedding功能可能不可用"
        log_warn "请启动Ollama: ollama serve"
    fi
}

init_database() {
    log_info "初始化数据库..."
    source venv/bin/activate
    python -c "from app.database import init_db; init_db(); print('数据库初始化完成')"
}

start_service() {
    local mode=$1
    
    case $mode in
        dev)
            log_info "启动开发模式（热重载）..."
            cd app
            uvicorn main:app --reload --host 0.0.0.0 --port 8001
            ;;
        prod)
            log_info "启动生产模式..."
            cd app
            nohup uvicorn main:app --host 0.0.0.0 --port 8001 > ../logs/app.log 2>&1 &
            echo $! > ../logs/app.pid
            log_info "服务已启动，PID: $(cat ../logs/app.pid)"
            log_info "日志文件: logs/app.log"
            ;;
        docker)
            log_info "启动Docker模式..."
            docker-compose up -d --build
            ;;
        *)
            log_error "未知模式: $mode"
            show_usage
            exit 1
            ;;
    esac
}

stop_service() {
    log_info "停止服务..."
    
    if [ -f "logs/app.pid" ]; then
        PID=$(cat logs/app.pid)
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            log_info "服务已停止 (PID: $PID)"
        else
            log_warn "进程不存在 (PID: $PID)"
        fi
        rm -f logs/app.pid
    fi
    
    if command -v docker-compose &> /dev/null; then
        docker-compose down 2>/dev/null || true
    fi
}

show_status() {
    log_info "服务状态:"
    
    if [ -f "logs/app.pid" ]; then
        PID=$(cat logs/app.pid)
        if kill -0 "$PID" 2>/dev/null; then
            log_info "FastAPI服务: 运行中 (PID: $PID)"
            
            if check_command curl; then
                HEALTH=$(curl -s http://localhost:8001/api/v1/health 2>/dev/null || echo "{}")
                log_info "健康检查: $HEALTH"
            fi
        else
            log_warn "FastAPI服务: 未运行 (PID文件存在但进程不存在)"
        fi
    else
        log_warn "FastAPI服务: 未运行"
    fi
    
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_info "Ollama: 运行中"
    else
        log_warn "Ollama: 未运行"
    fi
    
    if docker ps 2>/dev/null | grep -q biolid-cloud-agent_app; then
        log_info "Docker容器: 运行中"
    elif command -v docker-compose &> /dev/null; then
        log_warn "Docker容器: 未运行"
    fi
}

import_knowledge() {
    log_info "导入知识库..."
    source venv/bin/activate
    python scripts/import_knowledge.py --import
}

memory_reflection() {
    log_info "执行记忆反思..."
    source venv/bin/activate
    python scripts/memory_reflection.py ${1:-}
}

show_usage() {
    echo ""
    echo "BioLing Cloud Agent 管理脚本"
    echo ""
    echo "用法: $0 <命令> [参数]"
    echo ""
    echo "命令:"
    echo "  init              初始化环境（创建目录、安装依赖）"
    echo "  start [mode]      启动服务 (dev|prod|docker, 默认dev)"
    echo "  stop              停止服务"
    echo "  status            查看状态"
    echo "  restart           重启服务"
    echo "  import-kb         导入知识库"
    echo "  reflect [user_id] 执行记忆反思"
    echo "  logs              查看日志"
    echo "  shell             进入Python环境"
    echo ""
    echo "示例:"
    echo "  $0 init                    # 初始化环境"
    echo "  $0 start dev               # 开发模式启动"
    echo "  $0 start prod              # 生产模式启动"
    echo "  $0 start docker            # Docker模式启动"
    echo "  $0 stop                   # 停止服务"
    echo "  $0 import-kb              # 导入知识库"
    echo "  $0 reflect user_001       # 对用户执行记忆反思"
    echo ""
}

case "$1" in
    init)
        create_directories
        check_python
        install_dependencies
        check_env_file
        check_ollama
        init_database
        log_info "初始化完成！"
        ;;
    start)
        create_directories
        check_env_file
        start_service ${2:-dev}
        ;;
    stop)
        stop_service
        ;;
    status)
        show_status
        ;;
    restart)
        stop_service
        sleep 2
        start_service ${2:-prod}
        ;;
    import-kb)
        import_knowledge
        ;;
    reflect)
        memory_reflection $2
        ;;
    logs)
        if [ -f "logs/app.log" ]; then
            tail -f logs/app.log
        else
            log_error "日志文件不存在"
        fi
        ;;
    shell)
        source venv/bin/activate
        python
        ;;
    *)
        show_usage
        ;;
esac

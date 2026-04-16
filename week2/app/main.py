from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings, settings
from .db import db_connection, check_connection, DatabaseError
from .exceptions import setup_exception_handlers
from .routers import action_items, notes

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用程序生命周期管理"""
    # 启动时执行
    logger.info("=" * 50)
    logger.info("Starting Action Item Extractor Application")
    logger.info("=" * 50)
    
    # 配置日志系统
    settings.setup_logging()
    
    # 验证配置
    config_validation = settings.validate_configuration()
    if not config_validation["valid"]:
        logger.error("Configuration validation failed!")
        for issue in config_validation["issues"]:
            logger.error(f"  - {issue}")
        raise RuntimeError("Invalid configuration")
    
    # 初始化数据库
    try:
        db_connection.initialize_database()
        logger.info("Database initialized successfully")
    except DatabaseError as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # 检查LLM服务可用性（可选）
    llm_available = _check_llm_availability()
    if llm_available:
        logger.info(f"LLM service available (model: {settings.ollama_model})")
    else:
        logger.warning("LLM service not available - will use rule-based extraction")
    
    logger.info("Application startup completed successfully")
    logger.info("=" * 50)
    
    yield  # 应用运行期间
    
    # 关闭时执行
    logger.info("Shutting down application...")
    logger.info("Application shutdown completed")


def _check_llm_availability() -> bool:
    """检查LLM服务是否可用"""
    try:
        from ollama import chat
        
        response = chat(
            model=settings.ollama_model,
            messages=[{"role": "user", "content": "ping"}],
            options={"num_predict": 1}
        )
        
        return True
        
    except Exception as e:
        logger.debug(f"LLM availability check failed: {e}")
        return False


def create_application() -> FastAPI:
    """创建并配置FastAPI应用实例"""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="智能行动项提取服务 - 支持LLM和规则方法",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # 设置异常处理器
    setup_exception_handlers(app)
    
    # 注册路由
    app.include_router(notes.router)
    app.include_router(action_items.router)
    
    # 配置静态文件服务
    static_dir = settings.frontend_dir
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info(f"Static files mounted from: {static_dir}")
    else:
        logger.warning(f"Static files directory not found: {static_dir}")
    
    @app.get("/", response_class=HTMLResponse, tags=["root"])
    async def index() -> str:
        """返回前端页面"""
        html_path = static_dir / "index.html"
        if html_path.exists():
            return html_path.read_text(encoding="utf-8")
        raise HTTPException(status_code=404, detail="Frontend page not found")
    
    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        """健康检查端点"""
        db_connected = check_connection()
        llm_available = _check_llm_availability()
        
        status = "healthy" if db_connected else "degraded"
        
        return {
            "status": status,
            "version": settings.app_version,
            "database_connected": db_connected,
            "llm_available": llm_available,
            "configuration": {
                "app_name": settings.app_name,
                "debug_mode": settings.debug,
                "ollama_model": settings.ollama_model
            }
        }
    
    return app


# 创建应用实例
app = create_application()


if __name__ == "__main__":
    """直接运行时的入口点"""
    import sys
    
    # 使用配置中的主机和端口
    host = settings.host
    port = settings.port
    
    print(f"Starting server on {host}:{port}")
    print(f"Access the API at: http://{host}:{port}")
    print(f"API documentation at: http://{host}:{port}/docs")
    
    # 检查是否安装了uvicorn
    try:
        import uvicorn
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=True,
            log_level="info"
        )
    except ImportError:
        print("Error: uvicorn is not installed. Please install it with:")
        print("pip install uvicorn")
        print("Or use the command line to start the server:")
        print(f"uvicorn app.main:app --host {host} --port {port} --reload")
        sys.exit(1)
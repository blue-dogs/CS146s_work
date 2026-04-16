from __future__ import annotations

import logging
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from .schemas import ErrorResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """应用程序基础异常"""
    def __init__(
        self,
        message: str,
        error_code: str = "APP_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class ValidationError(AppError):
    """验证错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class NotFoundError(AppError):
    """资源未找到错误"""
    def __init__(self, resource_type: str, resource_id: Any):
        super().__init__(
            message=f"{resource_type} with ID {resource_id} not found",
            error_code="NOT_FOUND",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": str(resource_id)}
        )


class DatabaseError(AppError):
    """数据库操作错误"""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details={"original_error": str(original_error)} if original_error else {}
        )
        self.original_error = original_error


class LLMError(AppError):
    """LLM服务错误"""
    def __init__(self, message: str, model: str = ""):
        super().__init__(
            message=message,
            error_code="LLM_ERROR",
            status_code=503,
            details={"model": model} if model else {}
        )


class ExtractionError(AppError):
    """提取过程错误"""
    def __init__(self, message: str, method: str = ""):
        super().__init__(
            message=message,
            error_code="EXTRACTION_ERROR",
            status_code=422,
            details={"extraction_method": method} if method else {}
        )


def create_error_response(
    error: str,
    detail: str,
    status_code: int,
    timestamp: Optional[str] = None
) -> JSONResponse:
    """创建标准化的错误响应"""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=error,
            detail=detail,
            status_code=status_code,
            timestamp=timestamp or datetime.now().isoformat()
        ).dict()
    )


async def app_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理应用程序异常"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return create_error_response(
        error="INTERNAL_SERVER_ERROR",
        detail="服务器内部错误，请稍后重试",
        status_code=500
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """处理应用程序自定义错误"""
    logger.warning(f"App error: {exc.message}")
    
    response_data = {
        **exc.details,
        "error": exc.error_code,
        "detail": exc.message,
        "status_code": exc.status_code,
        "timestamp": datetime.now().isoformat()
    }
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_data
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """处理请求验证错误"""
    logger.warning(f"Validation error: {exc.errors()}")
    
    errors_detail = []
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"])
        errors_detail.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"]
        })
    
    return create_error_response(
        error="VALIDATION_ERROR",
        detail=f"请求验证失败: {len(errors_detail)} 个字段验证错误",
        status_code=422
    )


async def database_exception_handler(request: Request, exc: DatabaseError) -> JSONResponse:
    """处理数据库异常"""
    logger.error(f"Database error: {exc.message}")
    
    # 在生产环境中，不暴露原始错误详情
    from .config import get_settings
    settings = get_settings()
    
    if settings.debug:
        detail = f"{exc.message} - 原始错误: {str(exc.original_error)}"
    else:
        detail = "数据库操作失败，请稍后重试"
    
    return create_error_response(
        error="DATABASE_ERROR",
        detail=detail,
        status_code=exc.status_code
    )


async def llm_exception_handler(request: Request, exc: LLMError) -> JSONResponse:
    """处理LLM服务异常"""
    logger.warning(f"LLM error: {exc.message}")
    
    return create_error_response(
        error="LLM_SERVICE_UNAVAILABLE",
        detail=exc.message,
        status_code=503
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """为FastAPI应用设置异常处理器"""
    
    # 注册自定义异常处理器
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(DatabaseError, database_exception_handler)
    app.add_exception_handler(LLMError, llm_exception_handler)
    
    # 注册框架内置异常处理器
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # 注册通用异常处理器（最后注册，作为兜底）
    app.add_exception_handler(Exception, app_exception_handler)
    
    logger.info("Exception handlers configured successfully")


def handle_extraction_error(error: Exception, fallback_result: Any = None) -> tuple[bool, Any]:
    """
    统一处理提取过程中的错误
    
    Returns:
        (success, result): 是否成功及结果/错误信息
    """
    if isinstance(error, LLMError):
        logger.error(f"LLM extraction failed: {error.message}")
        return False, {"message": error.message, "fallback_used": True}
    
    elif isinstance(error, ExtractionError):
        logger.error(f"Extraction failed: {error.message}")
        return False, {"message": error.message}
    
    else:
        logger.error(f"Unexpected extraction error: {error}")
        if fallback_result is not None:
            return True, fallback_result
        raise error
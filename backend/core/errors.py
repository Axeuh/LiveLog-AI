"""
统一 API 响应格式和错误处理
"""
from enum import Enum
from typing import Any, Optional, List, Dict, Union
from pydantic import BaseModel
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import json

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """统一错误码"""
    AUTH_FAILED = "AUTH_FAILED"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    FORBIDDEN = "FORBIDDEN"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class ErrorDetail(BaseModel):
    """错误详情"""
    code: str
    message: str


class ApiResponse(BaseModel):
    """统一 API 响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[ErrorDetail] = None


def error_response(code: str, message: str, status_code: int = 400) -> JSONResponse:
    """快速创建错误响应"""
    return JSONResponse(
        status_code=status_code,
        content=ApiResponse(
            success=False,
            error=ErrorDetail(code=code, message=message)
        ).model_dump()
    )


def success_response(data: Any = None) -> JSONResponse:
    """快速创建成功响应"""
    return JSONResponse(
        content=ApiResponse(success=True, data=data).model_dump()
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """处理 HTTPException"""
    code_map = {
        401: ErrorCode.AUTH_FAILED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        422: ErrorCode.VALIDATION_ERROR,
        405: ErrorCode.NOT_IMPLEMENTED,
        503: ErrorCode.SERVICE_UNAVAILABLE,
    }
    error_code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse(
            success=False,
            error=ErrorDetail(code=error_code.value, message=str(exc.detail))
        ).model_dump()
    )


def _safe_json(val: Any, max_len: int = 500) -> str:
    """安全序列化（处理 bytes 和循环引用）"""
    try:
        def _convert(o):
            if isinstance(o, bytes):
                return f"<bytes len={len(o)}>"
            if isinstance(o, (set, frozenset)):
                return list(o)
            return o
        s = json.dumps(val, default=_convert, ensure_ascii=False)
        return s[:max_len] + "..." if len(s) > max_len else s
    except Exception:
        return str(val)[:max_len]


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """处理 RequestValidationError（FastAPI 请求体验证失败）"""
    errors = exc.errors()
    msg = errors[0]["msg"] if errors else "请求参数验证失败"
    logger.warning(f"[ValidationError] {request.method} {request.url.path}: {_safe_json(errors[:2])}")
    return JSONResponse(
        status_code=422,
        content=ApiResponse(
            success=False,
            error=ErrorDetail(code=ErrorCode.VALIDATION_ERROR.value, message=msg)
        ).model_dump()
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理未预期的异常"""
    logger.exception(f"Unhandled exception")
    return JSONResponse(
        status_code=500,
        content=ApiResponse(
            success=False,
            error=ErrorDetail(code=ErrorCode.INTERNAL_ERROR.value, message="服务器内部错误")
        ).model_dump()
    )

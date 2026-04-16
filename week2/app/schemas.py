from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Priority(str, Enum):
    """行动项优先级枚举"""
    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"


class Category(str, Enum):
    """任务类型分类"""
    DEVELOPMENT = "开发"
    TESTING = "测试"
    DOCUMENTATION = "文档"
    MEETING = "会议"
    DESIGN = "设计"
    DOWNLOAD = "下载"
    INSTALLATION = "安装"
    CONFIGURATION = "配置"
    GENERAL = "通用"


class ActionItemBase(BaseModel):
    """行动项基础模型"""
    description: str = Field(..., min_length=3, description="任务描述")
    priority: Optional[Priority] = Field(None, description="优先级")
    assignee: Optional[str] = Field(None, max_length=50, description="负责人")
    deadline: Optional[str] = Field(None, max_length=50, description="截止时间")
    category: Optional[Category] = Field(None, description="任务类型")
    estimated_time: Optional[str] = Field(None, max_length=20, description="预估时间")


class ActionItemCreate(ActionItemBase):
    """创建行动项请求模型"""
    pass


class ActionItemResponse(ActionItemBase):
    """行动项响应模型"""
    id: int = Field(..., description="行动项ID")
    note_id: Optional[int] = Field(None, description="关联笔记ID")
    done: bool = Field(False, description="是否完成")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="创建时间")
    extraction_method: str = Field("rule_based", description="提取方法")

    class Config:
        from_attributes = True


class NoteBase(BaseModel):
    """笔记基础模型"""
    content: str = Field(..., min_length=1, description="笔记内容")


class NoteCreate(NoteBase):
    """创建笔记请求模型"""
    pass


class NoteResponse(NoteBase):
    """笔记响应模型"""
    id: int = Field(..., description="笔记ID")
    created_at: str = Field(..., description="创建时间")

    class Config:
        from_attributes = True


class ExtractRequest(BaseModel):
    """提取请求模型"""
    text: str = Field(..., min_length=1, description="待提取的文本")
    save_note: bool = Field(False, description="是否保存为笔记")
    use_llm: bool = Field(True, description="是否使用LLM提取")


class ExtractResponse(BaseModel):
    """提取响应模型"""
    success: bool = Field(..., description="是否成功")
    action_items: List[ActionItemResponse] = Field(default_factory=list, description="提取的行动项列表")
    note_id: Optional[int] = Field(None, description="保存的笔记ID（如果保存）")
    extraction_method: str = Field(..., description="使用的提取方法（llm/rule_based）")
    message: Optional[str] = Field(None, description="附加消息")


class UpdateDoneRequest(BaseModel):
    """更新完成状态请求模型"""
    done: bool = Field(True, description="是否完成")


class UpdateDoneResponse(BaseModel):
    """更新完成状态响应模型"""
    id: int = Field(..., description="行动项ID")
    done: bool = Field(..., description="更新后的状态")
    message: str = Field("状态更新成功", description="操作结果消息")


class ErrorResponse(BaseModel):
    """标准错误响应模型"""
    error: str = Field(..., description="错误类型")
    detail: str = Field(..., description="错误详情")
    status_code: int = Field(..., description="HTTP状态码")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="错误发生时间")


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    database_connected: bool = Field(..., description="数据库连接状态")
    llm_available: bool = Field(..., description="LLM服务可用性")
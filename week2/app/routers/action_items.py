from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import db
from ..config import get_settings
from ..db import get_db, insert_note, insert_action_items
from ..exceptions import NotFoundError, DatabaseError, LLMError
from ..schemas import (
    ExtractRequest,
    ExtractResponse,
    ActionItemResponse,
    UpdateDoneRequest,
    UpdateDoneResponse,
)
from ..services.extract import extract_action_items_with_llm, _fallback_to_rule_based_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/action-items", tags=["action-items"])


@router.post(
    "/extract",
    response_model=ExtractResponse,
    summary="提取行动项",
    description="从文本中智能提取行动项（支持LLM和规则方法）"
)
async def extract_action_items(request: ExtractRequest) -> ExtractResponse:
    """
    从文本中提取行动项
    
    - **text**: 待提取的文本内容（必填）
    - **save_note**: 是否将原始文本保存为笔记（默认false）
    - **use_llm**: 是否使用LLM进行智能提取（默认true）
    
    返回提取的行动项列表，包含任务描述、优先级、负责人等详细信息
    """
    settings = get_settings()
    
    # 保存笔记（如果请求）
    note_id: Optional[int] = None
    if request.save_note:
        try:
            note_id = insert_note(request.text)
            logger.info(f"Saved note with ID: {note_id}")
        except DatabaseError as e:
            logger.warning(f"Failed to save note: {e}")
            # 笔记保存失败不应阻止提取过程
    
    # 执行提取
    extraction_method: str = "llm"
    action_items_data: List[Dict[str, Any]] = []
    
    if request.use_llm:
        try:
            logger.info("Starting LLM-based extraction")
            json_response = extract_action_items_with_llm(
                text=request.text,
                model_name=settings.ollama_model
            )
            
            parsed_data = json.loads(json_response)
            items_list = parsed_data.get("action_items", [])
            
            for item in items_list:
                item["extraction_method"] = "llm"
            
            action_items_data = items_list
            
        except LLMError as e:
            logger.warning(f"LLM extraction failed: {e.message}, falling back to rule-based")
            extraction_method = "rule_based"
            action_items_data = _perform_rule_based_extraction(request.text)
            
        except Exception as e:
            logger.error(f"Unexpected error during LLM extraction: {e}")
            extraction_method = "rule_based"
            action_items_data = _perform_rule_based_extraction(request.text)
    else:
        logger.info("Using rule-based extraction")
        extraction_method = "rule_based"
        action_items_data = _perform_rule_based_extraction(request.text)
    
    # 保存行动项到数据库
    saved_item_ids: List[int] = []
    if action_items_data:
        try:
            saved_item_ids = insert_action_items(action_items_data, note_id)
            logger.info(f"Saved {len(saved_item_ids)} action items to database")
        except DatabaseError as e:
            logger.error(f"Failed to save action items: {e}")
            # 保存失败不应阻止返回结果
    
    # 构建响应
    response_items = []
    for idx, item in enumerate(action_items_data):
        item_with_id = item.copy()
        if idx < len(saved_item_ids):
            item_with_id["id"] = saved_item_ids[idx]
        else:
            item_with_id["id"] = None
        
        item_with_id["note_id"] = note_id
        response_items.append(item_with_id)
    
    return ExtractResponse(
        success=True,
        action_items=response_items,
        note_id=note_id,
        extraction_method=extraction_method,
        message=f"成功提取 {len(response_items)} 个行动项（使用{extraction_method}方法）"
    )


def _perform_rule_based_extraction(text: str) -> List[Dict[str, Any]]:
    """执行基于规则的提取作为回退方案"""
    try:
        json_response = _fallback_to_rule_based_json(text)
        parsed_data = json.loads(json_response)
        items_list = parsed_data.get("action_items", [])
        
        for item in items_list:
            item["extraction_method"] = "rule_based"
        
        return items_list
        
    except Exception as e:
        logger.error(f"Rule-based extraction failed: {e}")
        return []


@router.post(
    "/extract-llm",
    response_model=ExtractResponse,
    summary="使用LLM提取行动项",
    description="专门使用LLM模型提取行动项，不进行规则方法回退"
)
async def extract_action_items_llm_only(
    request: ExtractRequest,
    db: Database = Depends(get_db)
) -> ExtractResponse:
    """
    专门使用LLM提取行动项
    
    - **text**: 输入文本
    - **save_note**: 是否保存为笔记（默认true）
    
    仅使用LLM方法，失败时直接返回空结果
    """
    settings = get_settings()
    extraction_method = "llm_only"
    
    # 创建笔记（如果需要）
    note_id = None
    if request.save_note:
        try:
            note_id = insert_note(request.text)
            logger.info(f"Created note {note_id} for extraction")
        except DatabaseError as e:
            logger.error(f"Failed to create note: {e}")
    
    # 仅使用LLM提取
    action_items_data = []
    try:
        logger.info("Starting LLM-only extraction")
        json_response = extract_action_items_with_llm(
            text=request.text,
            model_name=settings.ollama_model
        )
        
        parsed_data = json.loads(json_response)
        items_list = parsed_data.get("action_items", [])
        
        for item in items_list:
            item["extraction_method"] = "llm_only"
        
        action_items_data = items_list
        
    except Exception as e:
        logger.error(f"LLM-only extraction failed: {e}")
        # LLM失败时直接返回空结果，不进行回退
    
    # 保存行动项到数据库
    saved_item_ids: List[int] = []
    if action_items_data:
        try:
            saved_item_ids = insert_action_items(action_items_data, note_id)
            logger.info(f"Saved {len(saved_item_ids)} action items to database")
        except DatabaseError as e:
            logger.error(f"Failed to save action items: {e}")
    
    # 构建响应
    response_items = []
    for idx, item in enumerate(action_items_data):
        item_with_id = item.copy()
        if idx < len(saved_item_ids):
            item_with_id["id"] = saved_item_ids[idx]
        else:
            item_with_id["id"] = None
        
        item_with_id["note_id"] = note_id
        response_items.append(item_with_id)
    
    return ExtractResponse(
        success=True,
        action_items=response_items,
        note_id=note_id,
        extraction_method=extraction_method,
        message=f"成功提取 {len(response_items)} 个行动项（使用{extraction_method}方法）"
    )


@router.get(
    "",
    response_model=List[ActionItemResponse],
    summary="列出所有行动项",
    description="获取行动项列表（支持过滤和分页）"
)
async def list_all_action_items(
    note_id: Optional[int] = Query(default=None, description="按笔记ID过滤"),
    done_only: bool = Query(default=False, description="仅显示已完成项"),
    limit: int = Query(default=50, ge=1, le=100, description="每页数量"),
    offset: int = Query(default=0, ge=0, description="偏移量")
) -> List[ActionItemResponse]:
    """
    列出行动项
    
    - **note_id**: 按关联笔记过滤（可选）
    - **done_only**: 仅显示已完成的行动项（默认false）
    - **limit**: 每页数量（默认50，最大100）
    - **offset**: 分页偏移量（默认0）
    
    返回行动项列表，按创建时间倒序排列
    """
    try:
        items_data = db.list_action_items(note_id=note_id, done_only=done_only)
        
        # 应用分页（在内存中分页，生产环境应在数据库层面实现）
        paginated_items = items_data[offset:offset + limit]
        
        return [ActionItemResponse(**item) for item in paginated_items]
        
    except DatabaseError as e:
        logger.error(f"Failed to list action items: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error listing action items: {e}")
        raise HTTPException(status_code=500, detail="获取行动项列表失败")


@router.post(
    "/{action_item_id}/done",
    response_model=UpdateDoneResponse,
    summary="更新完成状态",
    description="标记或取消标记行动项为已完成"
)
async def mark_done(action_item_id: int, request: UpdateDoneRequest) -> UpdateDoneResponse:
    """
    更新行动项完成状态
    
    - **action_item_id**: 行动项ID（路径参数）
    - **done**: 是否完成（默认true）
    
    返回更新后的状态信息
    """
    try:
        result = db.update_action_item_done(action_item_id, request.done)
        logger.info(f"Updated action item {action_item_id} done status to {request.done}")
        return UpdateDoneResponse(**result)
        
    except DatabaseError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating action item {action_item_id}: {e}")
        raise HTTPException(status_code=500, detail="更新行动项状态失败")


@router.delete(
    "/{action_item_id}",
    summary="删除行动项",
    description="根据ID删除指定行动项"
)
async def delete_action_item(action_item_id: int) -> Dict[str, Any]:
    """
    删除行动项
    
    - **action_item_id**: 要删除的行动项ID
    
    返回操作结果
    """
    try:
        success = db.delete_action_item(action_item_id)
        logger.info(f"Deleted action item with ID: {action_item_id}")
        return {"success": True, "message": f"行动项 {action_item_id} 已删除"}
        
    except DatabaseError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error deleting action item {action_item_id}: {e}")
        raise HTTPException(status_code=500, detail="删除行动项失败")


@router.get(
    "/stats/summary",
    summary="获取统计摘要",
    description="获取行动项统计信息"
)
async def get_stats() -> Dict[str, Any]:
    """
    获取系统统计信息
    
    返回笔记和行动项的数量统计
    """
    try:
        stats = db.get_database_stats()
        settings = get_settings()
        
        return {
            **stats,
            "llm_model": settings.ollama_model,
            "use_llm_by_default": settings.use_llm_by_default
        }
        
    except DatabaseError as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
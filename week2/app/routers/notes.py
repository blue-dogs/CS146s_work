from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..config import get_settings
from ..exceptions import NotFoundError, DatabaseError, ValidationError
from ..schemas import (
    NoteCreate,
    NoteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notes", tags=["notes"])


@router.post(
    "",
    response_model=NoteResponse,
    status_code=201,
    summary="创建新笔记",
    description="创建一条新的笔记记录"
)
async def create_note(note: NoteCreate) -> NoteResponse:
    """
    创建新笔记
    
    - **content**: 笔记内容（必填）
    
    返回创建的笔记信息，包含自动生成的ID和创建时间
    """
    try:
        note_id = db.insert_note(note.content)
        note_data = db.get_note(note_id)
        
        if note_data is None:
            raise DatabaseError("笔记创建后无法获取数据")
        
        logger.info(f"Created note with ID: {note_id}")
        return NoteResponse(**note_data)
        
    except DatabaseError as e:
        logger.error(f"Failed to create note: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating note: {e}")
        raise HTTPException(status_code=500, detail="创建笔记失败")


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="获取单个笔记",
    description="根据ID获取特定笔记的详细信息"
)
async def get_single_note(note_id: int) -> NoteResponse:
    """
    获取单个笔记
    
    - **note_id**: 笔记ID（路径参数）
    
    返回指定ID的笔记内容
    """
    try:
        note_data = db.get_note(note_id)
        
        if note_data is None:
            raise NotFoundError("Note", note_id)
        
        return NoteResponse(**note_data)
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error getting note {note_id}: {e}")
        raise HTTPException(status_code=500, detail="获取笔记失败")


@router.get(
    "",
    response_model=List[NoteResponse],
    summary="列出所有笔记",
    description="分页获取笔记列表（按创建时间倒序）"
)
async def list_notes(
    limit: int = Query(default=50, ge=1, le=100, description="每页数量"),
    offset: int = Query(default=0, ge=0, description="偏移量")
) -> List[NoteResponse]:
    """
    列出所有笔记
    
    - **limit**: 每页返回数量（默认50，最大100）
    - **offset**: 分页偏移量（默认0）
    
    返回笔记列表，按创建时间倒序排列
    """
    try:
        notes_data = db.list_notes(limit=limit, offset=offset)
        return [NoteResponse(**note) for note in notes_data]
        
    except DatabaseError as e:
        logger.error(f"Failed to list notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error listing notes: {e}")
        raise HTTPException(status_code=500, detail="获取笔记列表失败")
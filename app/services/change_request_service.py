# app/services/change_request_service.py

from sqlalchemy import select

from typing import List, Dict, Any, Optional
from app.agents.update.meeting_summerize_agent import summarize_meeting_text
from app.schemas.request import ChangeRequestResultItem, MeetingActionItem
from app.models.document import Document

async def summarize_and_save_meeting(
    session,
    meeting_file_id: str,
    meeting_file: str
):
    # Source 가져오기
    result = await session.execute(
        select(Document).filter_by(doc_id=meeting_file_id)
    )
    source = result.scalars().first()
    if not source:
        raise ValueError(f"Source with id {meeting_file_id} not found")
    
    # 텍스트 요약 후 저장
    source.doc_description = summarize_meeting_text(meeting_file)
    await session.commit()
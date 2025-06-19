# app/services/change_request_service.py

from sqlalchemy import select

from typing import List, Dict, Any, Optional
from app.agents.update.meeting_analyzer_agent import extract_actions_from_meeting_text, summarize_meeting_text
from app.services.faiss_search_service import load_faiss_index_and_metadata, search_similar_requirements
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

def process_meeting_for_change_requests(
    meeting_minutes_text: str,
    faiss_index_name: str, # 예: "my_index.faiss"
    metadata_name: str,   # 예: "my_metadata.json"
    top_k_search: int = 1
) -> List[ChangeRequestResultItem]:

    faiss_index, existing_requirements_metadata = load_faiss_index_and_metadata(faiss_index_name, metadata_name)

    if not faiss_index or not existing_requirements_metadata:
        # 이 경우, 모든 논의를 '추가'로 간주하거나, 오류를 반환할 수 있음
        print("기존 요구사항 벡터 DB를 로드할 수 없어 모든 항목을 '추가' 후보로 처리하거나, 처리를 중단합니다.")
        # 여기서는 간단히 빈 리스트 반환 또는 예외 발생
        raise ValueError("기존 요구사항 벡터DB 로드 실패")

    action_candidates: List[MeetingActionItem] = extract_actions_from_meeting_text(meeting_minutes_text)
    final_cr_list: List[ChangeRequestResultItem] = []

    print(f"회의록에서 {len(action_candidates)}개의 변경/추가/삭제 후보 식별됨.")

    for candidate in action_candidates:
        cr_item_data = {
            "original_requirement_id": None,
            "original_description_name": None,
            "action_type": candidate.action_type,
            "updated_description_name": candidate.description_name if candidate.action_type in ["추가", "변경"] else None,
            "details_from_meeting": candidate.details,
            "reason_for_change": candidate.reason,
            "status": "제안됨", # 초기 상태
            "raw_text_from_meeting": candidate.raw_text_from_meeting,
            "similarity_score": None
        }

        if candidate.action_type in ["변경", "삭제"]:
            query_text_for_search = f"{candidate.description_name} {candidate.details}"
            search_results = search_similar_requirements(
                faiss_index,
                existing_requirements_metadata,
                query_text_for_search,
                top_k=top_k_search
            )
            if search_results:
                # 여기서는 가장 유사한 top_1 결과만 사용한다고 가정
                matched_req_meta, score = search_results[0]
                cr_item_data["original_requirement_id"] = matched_req_meta.get("id") # 메타데이터에 'id'가 있어야 함
                cr_item_data["original_description_name"] = matched_req_meta.get("description_name")
                cr_item_data["similarity_score"] = score
                
                # 상태 업데이트 로직 (예시)
                if candidate.action_type == "변경":
                    cr_item_data["status"] = "변경 제안"
                elif candidate.action_type == "삭제":
                    cr_item_data["status"] = "삭제 제안"

                print(f"  - '{candidate.description_name}' ({candidate.action_type}): 기존 '{matched_req_meta.get('description_name')}' (ID: {matched_req_meta.get('id')}) 매칭 (유사도: {score:.4f})")
        
        elif candidate.action_type == "추가":
            cr_item_data["status"] = "신규 제안"

        final_cr_list.append(ChangeRequestResultItem(**cr_item_data))
    
    return final_cr_list
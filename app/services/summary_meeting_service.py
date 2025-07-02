# app/services/summary_meeting_service.py
import asyncio
from sqlalchemy import select
from app.agents.update.meeting_summerize_agent import summarize_meeting_text
from app.models.document import Document
from app.core.mysql_config import get_mysql_db # 비동기 제너레이터로 DB 세션을 가져옴

async def process_meeting_summary_background(document_id: str, meeting_text: str):
    """
    백그라운드에서 독립적으로 실행되는 서비스 함수.
    DB 세션을 직접 열고, 에이전트를 호출하여 요약 결과를 저장합니다.
    """
    print(f"백그라운드 작업 시작: 문서 ID '{document_id}'의 회의록 요약")
    
    # 비동기 제너레이터를 사용하여 DB 세션을 생성하고 작업이 끝나면 자동으로 닫습니다.
    async for session in get_mysql_db():
        try:
            # 1. DB에서 문서 조회
            result = await session.execute(
                select(Document).filter_by(doc_id=document_id)
            )
            document_record = result.scalars().first()
            
            if not document_record:
                print(f"오류: 문서 ID '{document_id}'를 찾을 수 없습니다.")
                return # 작업을 중단

            # 2. 동기 함수인 에이전트를 별도 스레드에서 실행 (이벤트 루프 블로킹 방지)
            summary_html = await asyncio.to_thread(summarize_meeting_text, meeting_text)
            
            # 3. 요약 결과를 DB에 저장
            document_record.doc_description = summary_html
            await session.commit()
            
            print(f"성공: 문서 ID '{document_id}'에 요약이 성공적으로 저장되었습니다.")

        except Exception as e:
            print(f"오류: 백그라운드 요약 작업 중 예외 발생 - {e}")
            await session.rollback() # 오류 발생 시 롤백
        finally:
            # 세션은 async for 루프가 끝나며 자동으로 닫힙니다.
            pass
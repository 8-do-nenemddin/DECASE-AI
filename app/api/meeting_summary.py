# # app/api/v1/meeting_summary_router.py

# from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form, UploadFile, File
# from sqlalchemy.ext.asyncio import AsyncSession

# # 서비스 함수와 DB 세션 가져오기 함수를 임포트합니다.
# from app.services.summary_meeting_service import process_meeting_summary_background
# from app.core.mysql_config import get_mysql_db # DB 세션 의존성

# router = APIRouter()

# @router.post("/meetings/summarize", status_code=202)
# async def summarize_meeting_endpoint(
#     background_tasks: BackgroundTasks,
#     document_id: str = Form(..., description="요약을 저장할 문서의 ID"),
#     meeting_file: UploadFile = File(..., description="분석할 회의록 텍스트 파일"),
# ):
#     """
#     회의록 텍스트 파일을 업로드받아, 내용을 요약하고 지정된 문서 ID에 저장하는
#     백그라운드 작업을 시작합니다.
#     """
#     if not meeting_file.content_type == "text/plain":
#         raise HTTPException(status_code=400, detail="텍스트 파일(.txt)만 업로드할 수 있습니다.")

#     # 파일을 읽어서 텍스트 내용만 추출합니다.
#     contents = await meeting_file.read()
#     full_text = contents.decode('utf-8')

#     # 시간이 걸리는 작업을 백그라운드 태스크로 추가합니다.
#     background_tasks.add_task(
#         process_meeting_summary_background,
#         document_id=document_id,
#         meeting_text=full_text
#     )

#     return {"message": "회의록 요약 및 저장 작업이 백그라운드에서 시작되었습니다."}
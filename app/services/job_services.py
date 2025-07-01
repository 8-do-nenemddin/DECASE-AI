from datetime import datetime
from sqlalchemy import select

from app.models.job import Job, JobStatusEnum
from app.core.mysql_config import get_mysql_db

async def update_job_status_in_db(job_id: int, status: JobStatusEnum):
    """
    Job의 상태를 DB에 업데이트합니다. (결과 메시지 저장 기능 제외)
    """
    async for db in get_mysql_db():
        try:
            # job_id로 해당 작업 조회
            job = await db.scalar(select(Job).where(Job.job_id == job_id))
            if not job:
                print(f"Job with ID {job_id} not found.")
                return

            # 상태 업데이트
            job.status = status
            
            # 작업이 종료되는 상태(COMPLETED, FAILED, SUCCESS)일 경우 end_time 기록
            if status in [JobStatusEnum.COMPLETED, JobStatusEnum.FAILED, JobStatusEnum.SUCCESS]:
                job.end_time = datetime.now()

            await db.commit()
        
        except Exception as e:
            print(f"Failed to update job status for job_id {job_id}: {e}")
            await db.rollback()
        
        finally:
            # DB 세션/커넥션 닫기
            await db.close()
        
        break # async for 루프는 한 번만 실행
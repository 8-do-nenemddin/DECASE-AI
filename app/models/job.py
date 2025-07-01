from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class JobNameEnum(str, enum.Enum):
    SRS = "SRS"
    ASIS = "ASIS"
    MOCKUP = "MOCKUP"
    UPDATE = "UPDATE"

class JobStatusEnum(str, enum.Enum):
    PROCESSING = "PROCESSING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    SUCCESS = "SUCCESS"

class Job(Base):
    __tablename__ = "tm_jobs"

    job_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(Enum(JobNameEnum), nullable=False)
    project_id = Column(Integer, ForeignKey("tm_projects.project_id"), nullable=False)
    member_id = Column(Integer, ForeignKey("tn_members.member_id"))
    revision_count = Column(Integer, nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(Enum(JobStatusEnum), nullable=False)

    # 관계 설정 (옵션)
    project = relationship("Project")
    member = relationship("Member")
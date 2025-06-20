from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Document(Base):
    __tablename__ = "tm_documents"

    """
    doc_id 규칙
    - rfp 파일: RFP-{숫자}
    - 회의록 음성 : MOMV-{숫자}
    - 회의록 문서 : MOMD-{숫자}
    - 추가 파일 : EXTRA-{숫자}
    - 요구사항 정의서 : REQ-{숫자}
    - 조견표 : QFS-{숫자}
    - 매트릭스 : MATRIX-{숫자}
    - As-is : ASIS-{숫자}
    """
    doc_id = Column(String, primary_key=True)
    path = Column(String(1000), nullable=False)
    name = Column(String(100), nullable=False)
    doc_description = Column(String, nullable=True)
    created_date = Column(DateTime, nullable=False, default=datetime.now)
    is_member_upload = Column(Boolean, nullable=False, default=False)
    
    # Foreign Keys
    project_id = Column(Integer, ForeignKey('tm_projects.project_id'), nullable=False)
    member_id = Column(Integer, ForeignKey('tn_members.member_id'))
    
    # Relationships
    project = relationship("Project", back_populates="documents")
    member = relationship("Member", back_populates="documents")
    source = relationship("Source", back_populates="document", cascade="all, delete-orphan")

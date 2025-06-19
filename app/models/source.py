from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Source(Base):
    __tablename__ = "td_source"

    source_id = Column(Integer, primary_key=True, autoincrement=True)
    req_id_code = Column(String, nullable=True)
    doc_description = Column(String, nullable=True)
    page_num = Column(Integer, nullable=False)
    rel_sentence = Column(String(5000), nullable=False)
    
    # Foreign Keys
    req_pk = Column(Integer, ForeignKey('td_requirements.req_pk'), nullable=False)
    doc_id = Column(String, ForeignKey('tm_documents.doc_id'), nullable=False)
    
    # Relationships
    requirement = relationship("Requirement", back_populates="sources", lazy="select")
    document = relationship("Document", back_populates="source", lazy="select")

    def create_source(self, requirement, document, page_num: int, rel_sentence: str, req_id_code: str = None):
        """Create a new source record"""
        self.requirement = requirement
        self.document = document
        self.page_num = page_num
        self.rel_sentence = rel_sentence
        self.req_id_code = req_id_code 

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum
from app.database import Base

class Priority(PyEnum):
    HIGH = "HIGH"
    MIDDLE = "MIDDLE"
    LOW = "LOW"

    @classmethod
    def from_korean(cls, value: str) -> 'Priority':
        mapping = {
            "상": cls.HIGH,
            "중": cls.MIDDLE,
            "하": cls.LOW
        }
        if value not in mapping:
            raise ValueError(f"Unknown priority value: {value}")
        return mapping[value]

class Difficulty(PyEnum):
    HIGH = "HIGH"
    MIDDLE = "MIDDLE"
    LOW = "LOW"

    @classmethod
    def from_korean(cls, value: str) -> 'Difficulty':
        mapping = {
            "상": cls.HIGH,
            "중": cls.MIDDLE,
            "하": cls.LOW
        }
        if value not in mapping:
            raise ValueError(f"Unknown priority value: {value}")
        return mapping[value]

class RequirementType(PyEnum):
    FR = "FR"
    NFR = "NFR"

    @classmethod
    def from_korean(cls, value: str) -> 'RequirementType':
        if value is None:
            return None
            
        mapping = {
            "기능": cls.FR,
            "비기능": cls.NFR
        }
        if value not in mapping:
            raise ValueError(f"Unknown requirement type value: {value}")
        return mapping[value]


class Requirement(Base):
    __tablename__ = "td_requirements"

    req_pk = Column(Integer, primary_key=True, autoincrement=True)
    req_id_code = Column(String(100), nullable=False)
    revision_count = Column(Integer, nullable=False, default=1)
    type = Column(Enum(RequirementType))
    
    level_1 = Column(String(100))
    level_2 = Column(String(100))
    level_3 = Column(String(100))
    name = Column(String(100), nullable=False)
    description = Column(String(5000))
    
    priority = Column(Enum(Priority))
    difficulty = Column(Enum(Difficulty))
    created_date = Column(DateTime, nullable=False, default=datetime.now)
    is_deleted = Column(Boolean, default=False)
    deleted_revision = Column(Integer, nullable=False, default=0)
    project_id_aud = Column(BigInteger, default=False)
    modified_date = Column(DateTime, nullable=False, default=datetime.now)
    
    # Foreign Keys
    project_id = Column(Integer, ForeignKey('tm_projects.project_id'), nullable=False)
    member_id = Column(Integer, ForeignKey('tn_members.member_id'), nullable=False)
    
    mod_reason = Column(String)
    
    # Relationships
    project = relationship("Project", back_populates="requirements")
    member = relationship("Member", back_populates="requirements")
    sources = relationship("Source", back_populates="requirement", cascade="all, delete-orphan")

    def soft_delete(self, deleted_revision: int):
        """요구사항 정의서 soft delete"""
        self.is_deleted = True
        self.deleted_revision = deleted_revision

    def create_initial_requirement(self, req_id_code: str, type: RequirementType, 
                                 level_1: str, level_2: str, level_3: str,
                                 name: str, description: str, priority: Priority,
                                 difficulty: Difficulty, created_date: datetime,
                                 project_id: int, created_by_id: int, project_id_aud: int):
        """요구사항 정의서 초기 생성시 생성되는 데이터"""
        self.req_id_code = req_id_code
        self.revision_count = 1
        self.type = type
        self.level_1 = level_1
        self.level_2 = level_2
        self.level_3 = level_3
        self.name = name
        self.description = description
        self.priority = priority
        self.difficulty = difficulty
        self.created_date = created_date
        self.deleted_revision = 0  # 초기 요구사항은 삭제 x
        self.is_deleted = False
        self.project_id = project_id
        self.member_id = created_by_id
        self.mod_reason = ""  # 초기 요구사항 정의서의 수정 이유는 비워둠
        self.sources = []
        self.project_id_aud = project_id_aud
        self.modified_date = datetime.now()

    def create_update_requirement(self, req_id_code: str, revision_count: int,
                                mod_reason: str, type: RequirementType,
                                level_1: str, level_2: str, level_3: str,
                                name: str, description: str, priority: Priority,
                                difficulty: Difficulty, created_date: datetime,
                                project_id: int, created_by_id: int):
        """요구사항 정의서 수정시 추가되는 데이터"""
        self.req_id_code = req_id_code
        self.revision_count = revision_count
        self.type = type
        self.level_1 = level_1
        self.level_2 = level_2
        self.level_3 = level_3
        self.name = name
        self.description = description
        self.priority = priority
        self.difficulty = difficulty
        self.created_date = created_date
        self.is_deleted = False
        self.project_id = project_id
        self.member_id = created_by_id
        self.mod_reason = mod_reason  # 요구사항 추가 이유 
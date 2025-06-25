from datetime import datetime
from app.models.requirement import Requirement, RequirementType, Priority, Difficulty
from app.models.source import Source
from app.schemas.requirement import SrsRequirementData
from app.core.mysql_config import get_mysql_db

class RequirementService:
    def __init__(self, db=None):
        self.db = db

    async def initialize(self, db):
        self.db = db

    async def create_requirement(self, requirement_data: SrsRequirementData, member, project, document):
        if not self.db:
            raise ValueError("Database session not initialized")

        description = f"[대상 업무]\n{requirement_data.target_page}\n" \
                     f"[요건 처리 상세]\n{requirement_data.description}\n" 
        
        # 요구사항 엔티티 생성
        requirement = Requirement(
            req_id_code=requirement_data.requirement_id,
            revision_count=1,
            type=RequirementType.from_korean(requirement_data.type),
            level_1=requirement_data.category_large,
            level_2=requirement_data.category_medium,
            level_3=requirement_data.category_small,
            name=requirement_data.requirement_name,
            description=description,
            priority=Priority.from_korean(requirement_data.importance),
            difficulty=Difficulty.from_korean(requirement_data.difficulty),
            created_date=datetime.now(),
            is_deleted=False,
            deleted_revision=0,
            project_id=project.project_id,
            member_id=member.member_id,
            mod_reason="",
            project_id_aud=project.project_id,
            modified_date=datetime.now()
        )
        self.db.add(requirement)
        await self.db.flush()

        # 소스 엔티티 생성
        for source_data in requirement_data.sources:
            source = Source()
            source.create_source(
                requirement=requirement,
                document=document,
                page_num=source_data.source_page,
                rel_sentence=source_data.original_text,
                req_id_code=requirement.req_id_code
            )
            self.db.add(source)
        await self.db.flush()

        await self.db.commit()

        return requirement
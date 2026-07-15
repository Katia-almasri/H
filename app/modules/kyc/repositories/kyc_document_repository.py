"""KYC document repository."""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.kyc.models.kyc_document import KYCDocument


class KYCDocumentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, document_id: str) -> Optional[KYCDocument]:
        result = await self.db.execute(
            select(KYCDocument).where(KYCDocument.id == document_id)
        )
        return result.scalars().first()

    async def get_by_file_name(self, file_name: str) -> Optional[KYCDocument]:
        result = await self.db.execute(
            select(KYCDocument).where(KYCDocument.file_name == file_name)
        )
        return result.scalars().first()

    async def get_by_submission(self, submission_id: str) -> List[KYCDocument]:
        result = await self.db.execute(
            select(KYCDocument).where(KYCDocument.submission_id == submission_id)
        )
        return list(result.scalars().all())

    async def create(self, document: KYCDocument) -> KYCDocument:
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        return document

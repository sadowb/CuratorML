from __future__ import annotations

from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

# Define a generic type variable for our repository base class
# This allows us to type hint the methods in the base repository class to work with any model type.
ModelT = TypeVar("ModelT")


class RepositoryBase:
    async def _create(self, db: AsyncSession, instance: ModelT) -> ModelT:
        db.add(instance)
        await db.flush()
        await db.refresh(instance)
        return instance

    async def _delete(self, db: AsyncSession, instance: ModelT) -> None:
        await db.delete(instance)

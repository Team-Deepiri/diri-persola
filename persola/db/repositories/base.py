from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional, Dict, Any, Union
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import uuid

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository with common CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @property
    @abstractmethod
    def model_class(self):
        """Return the SQLAlchemy model class."""
        pass

    async def create(self, **kwargs) -> T:
        """Create a new record."""
        # Generate UUID if not provided
        if 'id' not in kwargs and hasattr(self.model_class, 'id'):
            kwargs['id'] = str(uuid.uuid4())

        instance = self.model_class(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: str) -> Optional[T]:
        """Get record by ID."""
        result = await self.session.execute(
            select(self.model_class).where(self.model_class.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all records with pagination."""
        result = await self.session.execute(
            select(self.model_class)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, id: str, **kwargs) -> Optional[T]:
        """Update record by ID."""
        # Remove None values
        update_data = {k: v for k, v in kwargs.items() if v is not None}

        if not update_data:
            return await self.get_by_id(id)

        result = await self.session.execute(
            update(self.model_class)
            .where(self.model_class.id == id)
            .values(**update_data)
            .returning(self.model_class)
        )
        updated = result.scalar_one_or_none()
        if updated:
            await self.session.refresh(updated)
        return updated

    async def delete(self, id: str) -> bool:
        """Delete record by ID."""
        result = await self.session.execute(
            delete(self.model_class).where(self.model_class.id == id)
        )
        return result.rowcount > 0

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filters."""
        query = select(func.count(self.model_class.id))

        if filters:
            conditions = []
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    conditions.append(getattr(self.model_class, key) == value)
            if conditions:
                query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return result.scalar()

    async def exists(self, id: str) -> bool:
        """Check if record exists."""
        result = await self.session.execute(
            select(func.count(self.model_class.id))
            .where(self.model_class.id == id)
        )
        return result.scalar() > 0

    async def bulk_create(self, items: List[Dict[str, Any]]) -> List[T]:
        """Bulk create multiple records."""
        instances = []
        for item_data in items:
            if 'id' not in item_data:
                item_data['id'] = str(uuid.uuid4())
            instance = self.model_class(**item_data)
            instances.append(instance)
            self.session.add(instance)

        await self.session.flush()
        for instance in instances:
            await self.session.refresh(instance)

        return instances

    async def bulk_update(self, updates: List[Dict[str, Any]]) -> int:
        """Bulk update multiple records. Each dict should have 'id' and update fields."""
        total_updated = 0
        for update_data in updates:
            id = update_data.pop('id')
            if await self.update(id, **update_data):
                total_updated += 1
        return total_updated

    async def bulk_delete(self, ids: List[str]) -> int:
        """Bulk delete multiple records."""
        result = await self.session.execute(
            delete(self.model_class).where(self.model_class.id.in_(ids))
        )
        return result.rowcount

    async def filter(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        skip: int = 0,
        limit: Optional[int] = None
    ) -> List[T]:
        """Filter records with optional ordering and pagination."""
        query = select(self.model_class)

        if filters:
            conditions = []
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    if isinstance(value, list):
                        conditions.append(getattr(self.model_class, key).in_(value))
                    else:
                        conditions.append(getattr(self.model_class, key) == value)
            if conditions:
                query = query.where(and_(*conditions))

        if order_by and hasattr(self.model_class, order_by):
            column = getattr(self.model_class, order_by)
            query = query.order_by(desc(column) if order_desc else asc(column))

        if limit:
            query = query.offset(skip).limit(limit)
        elif skip:
            query = query.offset(skip)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search(
        self,
        search_fields: List[str],
        query: str,
        skip: int = 0,
        limit: int = 50
    ) -> List[T]:
        """Full-text search across specified fields."""
        if not query or not search_fields:
            return await self.get_all(skip, limit)

        search_conditions = []
        for field in search_fields:
            if hasattr(self.model_class, field):
                column = getattr(self.model_class, field)
                search_conditions.append(column.ilike(f"%{query}%"))

        result = await self.session.execute(
            select(self.model_class)
            .where(or_(*search_conditions))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
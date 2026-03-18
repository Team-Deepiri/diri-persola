from typing import List, Optional, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models import AgentModel, PersonaModel
from ..schemas import AgentCreate, AgentUpdate


class AgentRepository(BaseRepository[AgentModel]):
    """Repository for agent operations."""

    @property
    def model_class(self):
        return AgentModel

    async def create_agent(self, agent_data: AgentCreate) -> AgentModel:
        """Create a new agent with persona link."""
        return await self.create(**agent_data.model_dump())

    async def get_agent(self, agent_id: str) -> Optional[AgentModel]:
        """Retrieve agent by ID."""
        return await self.get_by_id(agent_id)

    async def list_agents(
        self,
        skip: int = 0,
        limit: int = 50,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> List[AgentModel]:
        """List all agents with pagination."""
        return await self.filter(
            order_by=order_by,
            order_desc=order_desc,
            skip=skip,
            limit=limit
        )

    async def update_agent(self, agent_id: str, update_data: AgentUpdate) -> Optional[AgentModel]:
        """Update agent configuration."""
        return await self.update(agent_id, **update_data.model_dump(exclude_unset=True))

    async def delete_agent(self, agent_id: str) -> bool:
        """Remove agent."""
        return await self.delete(agent_id)

    async def get_agent_with_persona(self, agent_id: str) -> Optional[AgentModel]:
        """Retrieve agent with persona data loaded."""
        result = await self.session.execute(
            select(AgentModel)
            .options(selectinload(AgentModel.persona))
            .where(AgentModel.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def list_agents_by_persona(
        self,
        persona_id: str,
        skip: int = 0,
        limit: int = 50
    ) -> List[AgentModel]:
        """Get all agents using a specific persona."""
        return await self.filter(
            filters={"persona_id": persona_id},
            order_by="created_at",
            order_desc=True,
            skip=skip,
            limit=limit
        )

    async def update_agent_status(self, agent_id: str, is_active: bool) -> Optional[AgentModel]:
        """Update agent active/inactive state."""
        return await self.update(agent_id, is_active=is_active)

    async def get_active_agents(self, skip: int = 0, limit: int = 50) -> List[AgentModel]:
        """Get all active agents."""
        return await self.filter(
            filters={"is_active": True},
            order_by="created_at",
            order_desc=True,
            skip=skip,
            limit=limit
        )

    async def search_agents(self, query: str, skip: int = 0, limit: int = 50) -> List[AgentModel]:
        """Search agents by name."""
        return await self.search(
            search_fields=["name"],
            query=query,
            skip=skip,
            limit=limit
        )

    async def get_agents_with_persona_info(
        self,
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get agents with persona name included."""
        result = await self.session.execute(
            select(AgentModel, PersonaModel.name.label("persona_name"))
            .join(PersonaModel)
            .offset(skip)
            .limit(limit)
            .order_by(AgentModel.created_at.desc())
        )

        agents_info = []
        for row in result:
            agent, persona_name = row
            agent_dict = {
                "id": agent.id,
                "name": agent.name,
                "persona_id": agent.persona_id,
                "persona_name": persona_name,
                "config": agent.config,
                "is_active": agent.is_active,
                "created_at": agent.created_at,
                "updated_at": agent.updated_at,
            }
            agents_info.append(agent_dict)

        return agents_info

    async def count_agents_by_persona(self, persona_id: str) -> int:
        """Count agents using a specific persona."""
        return await self.count(filters={"persona_id": persona_id})

    async def bulk_update_agent_status(self, agent_ids: List[str], is_active: bool) -> int:
        """Bulk update active status for multiple agents."""
        updates = [{"id": agent_id, "is_active": is_active} for agent_id in agent_ids]
        return await self.bulk_update(updates)
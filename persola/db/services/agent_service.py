from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.agent_repository import AgentRepository
from ..repositories.persona_repository import PersonaRepository
from ..repositories.session_repository import SessionRepository
from ..repositories.message_repository import MessageRepository
from ..schemas import AgentCreate, AgentUpdate, MessageCreate, MessageRole
from ..models import AgentModel, PersonaModel, SessionModel


class AgentService:
    """Business logic for agent operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.agent_repo = AgentRepository(session)
        self.persona_repo = PersonaRepository(session)
        self.session_repo = SessionRepository(session)
        self.message_repo = MessageRepository(session)

    async def create_agent(self, agent_data: AgentCreate) -> AgentModel:
        """Create a new agent with persona linking."""
        # Validate persona exists
        persona = await self.persona_repo.get_persona(agent_data.persona_id)
        if not persona:
            raise ValueError(f"Persona with ID {agent_data.persona_id} not found")

        return await self.agent_repo.create_agent(agent_data)

    async def get_agent(self, agent_id: str) -> Optional[AgentModel]:
        """Retrieve agent by ID."""
        return await self.agent_repo.get_agent(agent_id)

    async def update_agent(self, agent_id: str, update_data: AgentUpdate) -> Optional[AgentModel]:
        """Update agent configuration."""
        return await self.agent_repo.update_agent(agent_id, update_data)

    async def delete_agent(self, agent_id: str) -> bool:
        """Remove agent."""
        return await self.agent_repo.delete_agent(agent_id)

    async def list_agents(
        self,
        skip: int = 0,
        limit: int = 50,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> List[AgentModel]:
        """List all agents."""
        return await self.agent_repo.list_agents(skip, limit, order_by, order_desc)

    async def get_agent_with_persona(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve agent with persona data."""
        agent = await self.agent_repo.get_agent_with_persona(agent_id)
        if not agent:
            return None

        return {
            "id": agent.id,
            "name": agent.name,
            "persona": {
                "id": agent.persona.id,
                "name": agent.persona.name,
                "description": agent.persona.description,
            },
            "config": agent.config,
            "is_active": agent.is_active,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        }

    async def invoke_agent(
        self,
        agent_id: str,
        user_message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute agent with persona and return response."""
        # Get agent with persona
        agent = await self.agent_repo.get_agent_with_persona(agent_id)
        if not agent:
            raise ValueError(f"Agent with ID {agent_id} not found")

        if not agent.is_active:
            raise ValueError(f"Agent {agent_id} is not active")

        # Create or get session
        if session_id:
            session = await self.session_repo.get_session(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
        else:
            session_data = {
                "persona_id": agent.persona_id,
                "agent_id": agent_id,
                "user_id": user_id,
            }
            session = await self.session_repo.create_session(session_data)

        # Add user message
        user_msg = MessageCreate(
            session_id=session.id,
            role=MessageRole.USER,
            content=user_message
        )
        await self.message_repo.add_message(user_msg)

        # Get conversation context
        context = await self.get_agent_context(agent_id, session.id)

        # Here you would call the LLM with the persona and context
        # For now, return a mock response
        ai_response = f"I am {agent.persona.name}. {agent.persona.description}\n\nYou said: {user_message}"

        # Add AI response
        ai_msg = MessageCreate(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=ai_response
        )
        await self.message_repo.add_message(ai_msg)

        return {
            "session_id": session.id,
            "response": ai_response,
            "agent": {
                "id": agent.id,
                "name": agent.name,
                "persona_name": agent.persona.name,
            },
        }

    async def get_agent_context(self, agent_id: str, session_id: str) -> Dict[str, Any]:
        """Build context for LLM including persona and conversation history."""
        agent = await self.agent_repo.get_agent_with_persona(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Get recent messages
        messages = await self.message_repo.get_recent_messages(session_id, limit=20)

        # Build system prompt from persona
        system_prompt = agent.persona.system_prompt or f"You are {agent.persona.name}."
        if agent.persona.description:
            system_prompt += f" {agent.persona.description}"

        # Add knob-based instructions
        knobs = agent.persona.get_knobs()
        if knobs.get("creativity", 0.5) > 0.7:
            system_prompt += " Be highly creative and imaginative."
        # Add more knob-based logic here...

        return {
            "system_prompt": system_prompt,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ],
            "persona_knobs": knobs,
            "agent_config": agent.config,
        }

    async def manage_session(
        self,
        agent_id: str,
        action: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle conversation flow management."""
        if action == "start":
            # Create new session
            agent = await self.get_agent(agent_id)
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            session = await self.session_repo.create_session({
                "persona_id": agent.persona_id,
                "agent_id": agent_id,
            })

            return {"action": "started", "session_id": session.id}

        elif action == "end" and session_id:
            # End session
            session = await self.session_repo.end_session(session_id)
            return {"action": "ended", "session_id": session_id}

        elif action == "clear" and session_id:
            # Clear conversation history
            count = await self.message_repo.delete_messages(session_id)
            return {"action": "cleared", "messages_deleted": count}

        else:
            raise ValueError(f"Invalid action: {action}")

    async def get_conversation_history(
        self,
        agent_id: str,
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get full conversation history."""
        # Verify agent owns the session
        session = await self.session_repo.get_session(session_id)
        if not session or session.agent_id != agent_id:
            raise ValueError("Session not found or not owned by agent")

        messages = await self.session_repo.get_session_messages(session_id, limit)

        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp,
                "metadata": msg.metadata_,
            }
            for msg in messages
        ]

    async def list_agents_by_persona(self, persona_id: str) -> List[AgentModel]:
        """Get agents using a specific persona."""
        return await self.agent_repo.list_agents_by_persona(persona_id)

    async def update_agent_status(self, agent_id: str, is_active: bool) -> Optional[AgentModel]:
        """Update agent active status."""
        return await self.agent_repo.update_agent_status(agent_id, is_active)

    async def get_active_agents(self) -> List[AgentModel]:
        """Get all active agents."""
        return await self.agent_repo.get_active_agents()

    async def search_agents(self, query: str) -> List[AgentModel]:
        """Search agents by name."""
        return await self.agent_repo.search_agents(query)
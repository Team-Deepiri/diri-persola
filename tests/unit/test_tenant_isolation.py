"""Multi-tenancy isolation tests.

Verifies that tenant-scoped repositories and the HTTP layer keep data
strictly partitioned: rows created by one tenant are invisible to others,
and per-tenant unique constraints allow same-name entities to coexist
across tenants while still rejecting duplicates within a tenant.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from persola.db.models import DEFAULT_TENANT, AgentModel, PersonaModel, SessionModel
from persola.db.repositories import (
    AgentRepository,
    MessageRepository,
    PersonaRepository,
    SessionRepository,
)
from persola.orchestration.memory import MemoryStore
from persola.orchestration.redis_memory import RedisTeamMemory

TENANT_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


async def _make_persona(db, tenant: UUID, name: str) -> PersonaModel:
    repo = PersonaRepository(db, tenant_id=tenant)
    return await repo.create(PersonaModel(name=name))


async def _make_agent(db, tenant: UUID, name: str) -> AgentModel:
    repo = AgentRepository(db, tenant_id=tenant)
    return await repo.create(AgentModel(name=name))


# ---------------------------------------------------------------------------
# Repository layer
# ---------------------------------------------------------------------------


async def test_create_stamps_tenant_id(db_session):
    persona = await _make_persona(db_session, TENANT_A, "Alpha")
    assert persona.tenant_id == TENANT_A


async def test_unscoped_repo_uses_default_tenant(db_session):
    persona = await _make_persona(db_session, None, "System Row")
    assert persona.tenant_id == DEFAULT_TENANT


async def test_persona_isolation_across_tenants(db_session):
    await _make_persona(db_session, TENANT_A, "Alpha")

    repo_b = PersonaRepository(db_session, tenant_id=TENANT_B)
    assert await repo_b.get_by_name("Alpha") is None
    assert await repo_b.list() == []
    assert await repo_b.count() == 0
    assert await repo_b.search("Alpha") == []

    repo_a = PersonaRepository(db_session, tenant_id=TENANT_A)
    assert (await repo_a.get_by_name("Alpha")) is not None
    assert await repo_a.count() == 1


async def test_get_update_delete_are_scoped(db_session):
    persona = await _make_persona(db_session, TENANT_A, "Alpha")

    repo_b = PersonaRepository(db_session, tenant_id=TENANT_B)
    assert await repo_b.get(persona.id) is None
    assert await repo_b.update(persona.id, {"description": "hijacked"}) is None
    assert await repo_b.delete(persona.id) is False

    repo_a = PersonaRepository(db_session, tenant_id=TENANT_A)
    assert (await repo_a.get(persona.id)) is not None


async def test_agent_isolation_across_tenants(db_session):
    await _make_agent(db_session, TENANT_A, "Helper")

    repo_b = AgentRepository(db_session, tenant_id=TENANT_B)
    assert await repo_b.get_by_name("Helper") is None
    assert await repo_b.list_active() == []

    repo_a = AgentRepository(db_session, tenant_id=TENANT_A)
    assert (await repo_a.get_by_name("Helper")) is not None
    assert len(await repo_a.list_active()) == 1


async def test_session_isolation_across_tenants(db_session):
    agent = await _make_agent(db_session, TENANT_A, "Chat Agent")
    session_repo_a = SessionRepository(db_session, tenant_id=TENANT_A)
    session = await session_repo_a.create(
        SessionModel(agent_id=agent.id, session_id="conv-1")
    )

    session_repo_b = SessionRepository(db_session, tenant_id=TENANT_B)
    assert await session_repo_b.get_by_session_id("conv-1") is None

    session_repo_a2 = SessionRepository(db_session, tenant_id=TENANT_A)
    assert await session_repo_a2.get_by_session_id("conv-1") is not None
    assert (await session_repo_a2.get(session.id)) is not None


async def test_message_isolation_across_tenants(db_session):
    agent = await _make_agent(db_session, TENANT_A, "Chat Agent")
    session = await SessionRepository(db_session, tenant_id=TENANT_A).create(
        SessionModel(agent_id=agent.id, session_id="conv-1")
    )
    message_repo_a = MessageRepository(db_session, tenant_id=TENANT_A)
    await message_repo_a.add(session.id, "user", "hello")

    message_repo_b = MessageRepository(db_session, tenant_id=TENANT_B)
    assert await message_repo_b.get_history(session.id) == []

    history_a = await MessageRepository(db_session, tenant_id=TENANT_A).get_history(session.id)
    assert len(history_a) == 1
    assert history_a[0].content == "hello"


async def test_same_name_allowed_across_tenants(db_session):
    await _make_persona(db_session, TENANT_A, "Shared Name")
    await _make_persona(db_session, TENANT_B, "Shared Name")

    assert await PersonaRepository(db_session, tenant_id=TENANT_A).count() == 1
    assert await PersonaRepository(db_session, tenant_id=TENANT_B).count() == 1


async def test_same_name_rejected_within_tenant(db_session):
    await _make_persona(db_session, TENANT_A, "Dup")
    with pytest.raises(IntegrityError):
        await _make_persona(db_session, TENANT_A, "Dup")


async def test_same_session_id_allowed_across_tenants(db_session):
    agent_a = await _make_agent(db_session, TENANT_A, "A Agent")
    agent_b = await _make_agent(db_session, TENANT_B, "B Agent")

    await SessionRepository(db_session, tenant_id=TENANT_A).create(
        SessionModel(agent_id=agent_a.id, session_id="same-id")
    )
    await SessionRepository(db_session, tenant_id=TENANT_B).create(
        SessionModel(agent_id=agent_b.id, session_id="same-id")
    )

    assert await SessionRepository(db_session, tenant_id=TENANT_A).count() == 1
    assert await SessionRepository(db_session, tenant_id=TENANT_B).count() == 1


async def test_same_session_id_rejected_within_tenant(db_session):
    agent = await _make_agent(db_session, TENANT_A, "Agent")
    session_repo = SessionRepository(db_session, tenant_id=TENANT_A)
    await session_repo.create(SessionModel(agent_id=agent.id, session_id="dup"))
    with pytest.raises(IntegrityError):
        await session_repo.create(SessionModel(agent_id=agent.id, session_id="dup"))


# ---------------------------------------------------------------------------
# In-memory memory isolation
# ---------------------------------------------------------------------------


def test_memory_store_isolation_by_tenant():
    store = MemoryStore()
    store.store("session-1", "goal", "write a novel", tenant_id=str(TENANT_A))
    store.store("session-1", "goal", "take a nap", tenant_id=str(TENANT_B))

    assert store.recall("session-1", "goal", tenant_id=str(TENANT_A)) == "write a novel"
    assert store.recall("session-1", "goal", tenant_id=str(TENANT_B)) == "take a nap"

    hits_a = store.search("session-1", "novel", tenant_id=str(TENANT_A))
    assert len(hits_a) == 1 and hits_a[0]["value"] == "write a novel"
    assert store.search("session-1", "novel", tenant_id=str(TENANT_B)) == []

    store.clear_session("session-1", tenant_id=str(TENANT_A))
    assert store.recall("session-1", "goal", tenant_id=str(TENANT_A)) is None
    assert store.recall("session-1", "goal", tenant_id=str(TENANT_B)) == "take a nap"


def test_redis_team_memory_key_namespacing():
    memory = RedisTeamMemory()
    scoped = memory._hash_key("session-1", str(TENANT_A))
    assert scoped == f"{RedisTeamMemory.KEY_PREFIX}:{TENANT_A}:session-1"
    assert memory._hash_key("session-1") == f"{RedisTeamMemory.KEY_PREFIX}:session-1"


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------


async def test_api_persona_isolation(db_session):
    from httpx import ASGITransport, AsyncClient

    from persola.api.main import app
    from persola.auth import get_request_tenant_id
    from persola.db.database import get_db

    async def _override_get_db():
        yield db_session

    async def _client_for(tenant: UUID):
        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_request_tenant_id] = lambda: tenant
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async with await _client_for(TENANT_A) as client_a:
        res = await client_a.post(
            "/api/v1/personas",
            json={"name": "Tenant A Persona", "description": "private"},
        )
        assert res.status_code == 200, res.text

    async with await _client_for(TENANT_B) as client_b:
        res = await client_b.get("/api/v1/personas")
        assert res.status_code == 200, res.text
        assert res.json() == []

    async with await _client_for(TENANT_A) as client_a2:
        res = await client_a2.get("/api/v1/personas")
        assert len(res.json()) == 1
        assert res.json()[0]["name"] == "Tenant A Persona"

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Work queue / org chart / audit log isolation
# ---------------------------------------------------------------------------


async def test_org_chart_isolation_across_tenants(db_session):
    from persola.orchestration.org_chart import GLOBAL_ORG_CHART, OrgNode

    custom_role = "custom-tenant-a-role"
    await GLOBAL_ORG_CHART.upsert_node(
        "default",
        OrgNode(role=custom_role, title="Tenant A Only"),
        session=db_session,
        tenant_id=TENANT_A,
    )
    await db_session.commit()

    # Each tenant gets its own seeded chart, so a tenant-A-only custom role must
    # never appear in tenant B's chart.
    chart_b = await GLOBAL_ORG_CHART.to_dict("default", session=db_session, tenant_id=TENANT_B)
    assert custom_role not in {node["role"] for node in chart_b["nodes"]}

    chart_a = await GLOBAL_ORG_CHART.to_dict("default", session=db_session, tenant_id=TENANT_A)
    roles_a = {node["role"] for node in chart_a["nodes"]}
    assert custom_role in roles_a


async def test_task_queue_isolation_across_tenants(db_session):
    from persola.orchestration.task_queue import GLOBAL_TASK_QUEUE

    await GLOBAL_TASK_QUEUE.enqueue(
        team_id="default",
        role="executor",
        subtask="private subtask for A",
        origin="user",
        session_id="sess-a",
        tenant_id=TENANT_A,
        session=db_session,
    )
    await db_session.commit()

    board_b = await GLOBAL_TASK_QUEUE.board("default", session=db_session, tenant_id=TENANT_B)
    assert all(col == [] for col in board_b.values())

    board_a = await GLOBAL_TASK_QUEUE.board("default", session=db_session, tenant_id=TENANT_A)
    subtasks = [t["subtask"] for col in board_a.values() for t in col]
    assert "private subtask for A" in subtasks


async def test_audit_log_isolation_across_tenants(db_session):
    from persola.db.models import AuditEventType
    from persola.orchestration.audit_log import GLOBAL_AUDIT_LOG

    await GLOBAL_AUDIT_LOG.record(
        team_id="default",
        event_type=AuditEventType.INSTRUCTION,
        actor="user",
        recipient="coordinator",
        summary="secret event for A",
        session_id="sess-a",
        tenant_id=TENANT_A,
        session=db_session,
    )
    await db_session.commit()

    timeline_b = await GLOBAL_AUDIT_LOG.timeline(
        "default", session=db_session, tenant_id=TENANT_B
    )
    assert timeline_b == []

    timeline_a = await GLOBAL_AUDIT_LOG.timeline(
        "default", session=db_session, tenant_id=TENANT_A
    )
    assert len(timeline_a) == 1
    assert timeline_a[0]["summary"] == "secret event for A"
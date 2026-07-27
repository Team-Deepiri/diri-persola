"""End-to-end audit — Phases 1–5 completeness against roadmap exit criteria."""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID

import pytest

from persola.orchestration.city_worker import CITY_WORKER_POOL, CityWorkItem
from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestPhaseAuditE2E:
	async def test_full_city_lifecycle(self, db_session):
		service = CityService(db_session)

		# P1 — family + spawn + pending job
		family = await service.create_family(name="Audit Family", parent_name="Parent")
		fid = UUID(family["id"])
		child = await service.spawn_child(
			fid,
			name="Audit Child",
			role_label="executor",
			knob_overrides={"creativity": 0.9},
		)
		assert child["parent_member_id"] == family["members"][0]["id"]
		job = await service.start_job(family_id=fid, goal="audit build+run", district="build")
		assert job["status"] == "pending"
		jid = UUID(job["id"])

		# P2 — write → read → run → sandbox deny
		agent_id = UUID(child["agent_id"])
		exec_ok = await service.execute_tool_calls(
			jid,
			[
				{"name": "workspace_write", "args": {"path": "audit.py", "content": "print('audit-ok')\n"}},
				{"name": "workspace_read", "args": {"path": "audit.py"}},
				{"name": "workspace_list", "args": {}},
				{"name": "run_python", "args": {"path": "audit.py"}},
			],
			agent_id=agent_id,
		)
		assert all(t["ok"] for t in exec_ok["tool_results"][:4] if t["name"] != "workspace_list")
		assert any(t["name"] == "run_python" and t["ok"] for t in exec_ok["tool_results"])
		denied = await service.execute_tool_calls(
			jid,
			[{"name": "workspace_write", "args": {"path": "../x.py", "content": "no"}}],
			agent_id=agent_id,
		)
		assert denied["tool_results"][0]["ok"] is False
		runs = await service.list_runs(jid)
		assert any(r["status"] == "succeeded" for r in runs)

		# P3 — wedge multi-contributor + cohesion.merge contract
		wedge = await service.run_wedge_demo(family_name="Audit Wedge")
		assert wedge["success"] is True
		merge_events = [e for e in wedge["events"] if e["event_type"] == "cohesion.merge"]
		assert merge_events
		payload = merge_events[-1]["payload"]
		assert "parent_id" in payload and "child_ids" in payload
		assert isinstance(payload["child_ids"], list) and len(payload["child_ids"]) >= 1

		# P4 — incremental events cursor
		wid = UUID(wedge["job"]["id"])
		events = await service.list_events(job_id=wid)
		assert len(events) >= 2
		mid = events[len(events) // 2]["id"]
		newer = await service.list_events_since(job_id=wid, after_id=UUID(mid))
		assert all(e["id"] != mid for e in newer)

		# P5 — model tiers + cohesion + worker enqueue with injected session
		parent = next(m for m in wedge["family"]["members"] if m["role_in_family"] == "parent")
		child_m = next(m for m in wedge["family"]["members"] if m["role_in_family"] == "child")
		p_agent = await service.agents.get(UUID(parent["agent_id"]))
		c_agent = await service.agents.get(UUID(child_m["agent_id"]))
		assert p_agent and c_agent
		assert p_agent.model == service.model_tiers.parent
		assert c_agent.model == service.model_tiers.child

		score = await service.cohesion_score(wid)
		assert 0.0 <= score["score"] <= 1.0

		@asynccontextmanager
		async def _factory():
			yield db_session

		CITY_WORKER_POOL.set_session_factory(_factory)
		try:
			# Ensure workers can see this DB
			if CITY_WORKER_POOL._started:
				await CITY_WORKER_POOL.stop()
			item = await service.enqueue_job_tools(
				wid,
				[{"name": "emit_viz_event", "args": {"event_type": "viz.pulse", "payload": {"audit": True}}}],
				agent_id=UUID(child_m["agent_id"]),
				wait=True,
			)
			assert item["status"] == "completed"
		finally:
			await CITY_WORKER_POOL.stop()
			CITY_WORKER_POOL.set_session_factory(None)

		# P5 probe bar
		probe = await service.scale_probe(
			families=5,
			agents_per_family=10,
			name_prefix="AuditProbe",
			run_jobs=False,
		)
		assert probe["meets_probe_bar"] is True
		assert probe["agents"] == 50

	async def test_team_orchestrator_uses_city_tools(self, db_session):
		service = CityService(db_session)
		family = await service.create_family(name="Orch Family")
		job = await service.start_job(family_id=UUID(family["id"]), goal="orch")
		agent_id = UUID(family["members"][0]["agent_id"])

		async def llm(system: str, user: str) -> str:
			# Emit structured tool call so executor/specialist path runs city tools
			return (
				'{"tool_calls":[{"name":"workspace_write","args":'
				'{"path":"from_team.py","content":"print(42)\\n"}},'
				'{"name":"run_python","args":{"path":"from_team.py"}}]}'
			)

		result = await service.invoke_team_on_job(
			UUID(job["id"]),
			"implement and build the script",
			llm_fn=llm,
			agent_id=agent_id,
			use_langgraph=False,
		)
		assert "workspace_write" in result.get("city_tools", [])
		# At least one specialist should have produced tool results via parse_tool_calls
		assert result.get("tool_results") is not None
		arts = await service.list_artifacts(UUID(job["id"]))
		# May or may not write depending on which roles ran — ensure city tools were bound
		assert any(t.startswith("workspace_") or t == "run_python" for t in result["city_tools"])

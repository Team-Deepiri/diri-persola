"""Phase 9 — Austin export pack + disk commons mirror."""

from __future__ import annotations

from pathlib import Path

import pytest

from persola.orchestration.commons_mirror import list_mirrored_files, mirror_artifact, mirror_status
from persola.services.city_service import CityService

pytestmark = pytest.mark.anyio


class TestCommonsMirror:
    def test_mirror_writes_under_root(self, tmp_path: Path):
        job_id = "00000000-0000-0000-0000-000000000099"
        result = mirror_artifact(
            job_id=job_id,
            path="build/hello.py",
            content='print("hi")\n',
            root=tmp_path,
        )
        assert result["mirrored"] is True
        files = list_mirrored_files(job_id, root=tmp_path)
        assert "build/hello.py" in files
        assert (tmp_path / "jobs" / job_id / "build" / "hello.py").read_text() == 'print("hi")\n'

    def test_mirror_disabled_without_env(self, monkeypatch):
        monkeypatch.delenv("PERSOLA_CITY_COMMONS_ROOT", raising=False)
        assert mirror_status()["enabled"] is False
        assert mirror_artifact(job_id="x", path="a.py", content="1")["mirrored"] is False


class TestAustinExport:
    async def test_export_pack_shape(self, db_session, tmp_path, monkeypatch):
        monkeypatch.setenv("PERSOLA_CITY_COMMONS_ROOT", str(tmp_path))
        service = CityService(db_session)
        await service.scale_probe(families=2, agents_per_family=3, name_prefix="P9", run_jobs=True)
        pack = await service.export_austin_pack(event_limit=50, include_artifacts=True)
        assert pack["pack_version"] == "1.3"
        assert pack["vitals"]["agent_count"] >= 6
        assert len(pack["graph"]["nodes"]) >= 6
        assert len(pack["graph"]["edges"]) >= 1
        assert isinstance(pack["events"], list)
        assert "chronicle" in pack
        assert "generations" in pack
        assert pack["commons_mirror"]["enabled"] is True
        assert "export" in pack["hints"]

        # Disk mirror should have probe artifacts
        job_id = pack["artifacts"][0]["job_id"] if pack["artifacts"] else None
        if job_id:
            files = list_mirrored_files(job_id, root=tmp_path)
            assert any(f.endswith(".py") for f in files)

    async def test_export_and_commons_api(self, http_client, tmp_path, monkeypatch):
        monkeypatch.setenv("PERSOLA_CITY_COMMONS_ROOT", str(tmp_path))
        seed = await http_client.post("/api/v1/city/wedge/seed", json={"name": "ExportSeed"})
        assert seed.status_code == 200
        run = await http_client.post(
            "/api/v1/city/wedge/run", json={"family_id": seed.json()["id"]}
        )
        assert run.status_code == 200

        export = await http_client.get("/api/v1/city/export/austin")
        assert export.status_code == 200
        body = export.json()
        assert body["pack_version"] == "1.3"
        assert len(body["graph"]["nodes"]) >= 1
        assert "generations" in body

        status = await http_client.get("/api/v1/city/commons/status")
        assert status.status_code == 200
        assert status.json()["enabled"] is True

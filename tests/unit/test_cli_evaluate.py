"""Unit tests for the `persola evaluate` command group.

The Helox SDK is an optional dependency (`poetry install --with eval`) that
drags in torch/transformers, so every test here stubs the harness rather than
importing the real one. That keeps the suite runnable on a bare install.
"""

import sys
import types
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from persola.cli.commands import evaluate as evaluate_mod
from persola.cli.main import cli


class FakeHarness:
    """Minimal stand-in for AutomaticEvaluationHarness."""

    def __init__(self, suites=None):
        self.suites = list(suites or ["code_generation"])
        self.loaded_from = None
        self.evaluated = []

    def load_suites_from_dir(self, suite_dir):
        self.loaded_from = Path(suite_dir)
        return {name: [] for name in self.suites}

    def load_test_suite(self, suite_name, test_file):
        self.loaded_from = Path(test_file)
        self.suites.append(suite_name)
        return []

    def list_suites(self):
        return list(self.suites)

    def evaluate_subject(self, subject, suite_name, **kwargs):
        self.evaluated.append((subject.name, suite_name, kwargs))
        return {
            "suite_name": suite_name,
            "passed_tests": 2,
            "total_tests": 3,
            "avg_score": 0.5,
            "passed": False,
        }


@pytest.fixture()
def fake_harness(monkeypatch, tmp_path):
    """Install a FakeHarness and point the default suite dir at a real dir."""
    harness = FakeHarness()
    monkeypatch.setattr(evaluate_mod, "_harness", lambda eval_dir: harness)
    monkeypatch.setattr(evaluate_mod, "_sdk_suite_dir", lambda: tmp_path)
    return harness


def run(*args):
    return CliRunner().invoke(cli, ["evaluate", *args])


# ---------------------------------------------------------------------------
# Subject selection
# ---------------------------------------------------------------------------

def test_run_rejects_both_agent_and_model(fake_harness):
    result = run("run", "--suite", "code_generation", "--agent", "a1", "--model", "/m")
    assert result.exit_code != 0
    assert "exactly one of --agent or --model" in result.output


def test_run_rejects_neither_agent_nor_model(fake_harness):
    result = run("run", "--suite", "code_generation")
    assert result.exit_code != 0
    assert "exactly one of --agent or --model" in result.output


# ---------------------------------------------------------------------------
# Suite loading
# ---------------------------------------------------------------------------

def test_run_rejects_unknown_suite(fake_harness):
    result = run("run", "--suite", "nope", "--agent", "a1")
    assert result.exit_code != 0
    assert "not found" in result.output
    assert "code_generation" in result.output


def test_run_rejects_missing_suite_dir(fake_harness, tmp_path):
    missing = tmp_path / "does-not-exist"
    result = run(
        "run", "--suite", "code_generation", "--agent", "a1", "--suite-dir", str(missing)
    )
    assert result.exit_code != 0
    assert "suite dir/file not found" in result.output


def test_run_defaults_to_sdk_suite_dir(fake_harness, tmp_path, monkeypatch):
    monkeypatch.setattr(
        evaluate_mod, "_agent_subject", lambda client, agent_id: _named(f"agent:{agent_id}")
    )
    result = run("run", "--suite", "code_generation", "--agent", "a1", "--format", "table")
    assert result.exit_code == 0, result.output
    assert fake_harness.loaded_from == tmp_path
    assert "2/3 passed" in result.output


def _named(name):
    subject = type("Subject", (), {})()
    subject.name = name
    return subject


# ---------------------------------------------------------------------------
# Agent subject error handling
# ---------------------------------------------------------------------------

class FakeClient:
    def __init__(self, payload):
        self.payload = payload

    def api_request(self, method, path, **kwargs):
        return self.payload


class _StubCallableGenerator:
    """Stands in for the SDK's CallableGenerator: fn(prompt, max_new_tokens)."""

    def __init__(self, fn, name=None):
        self.fn = fn
        self.name = name

    def generate(self, prompt, max_new_tokens=100):
        return self.fn(prompt, max_new_tokens)


@pytest.fixture()
def stub_subjects(monkeypatch):
    """Provide deepiri_helox_sdk.evaluation.subjects without installing the SDK."""
    subjects = types.ModuleType("deepiri_helox_sdk.evaluation.subjects")
    subjects.CallableGenerator = _StubCallableGenerator
    for name in ("deepiri_helox_sdk", "deepiri_helox_sdk.evaluation"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "deepiri_helox_sdk.evaluation.subjects", subjects)
    return subjects


def test_agent_subject_returns_response_text(stub_subjects):
    subject = evaluate_mod._agent_subject(FakeClient({"response": "hi"}), "a1")
    assert subject.generate("prompt", 10) == "hi"
    assert subject.name == "agent:a1"


def test_agent_subject_raises_when_response_missing(stub_subjects):
    subject = evaluate_mod._agent_subject(FakeClient({"detail": "boom"}), "a1")
    with pytest.raises(click.ClickException) as excinfo:
        subject.generate("prompt", 10)
    assert "no 'response' field" in str(excinfo.value)


def test_agent_subject_raises_on_non_dict_payload(stub_subjects):
    subject = evaluate_mod._agent_subject(FakeClient("plain string"), "a1")
    with pytest.raises(click.ClickException):
        subject.generate("prompt", 10)


# ---------------------------------------------------------------------------
# Optional dependency handling
# ---------------------------------------------------------------------------

def test_missing_sdk_reports_install_hint(monkeypatch):
    def _boom(eval_dir):
        raise click.ClickException(evaluate_mod._INSTALL_HINT)

    monkeypatch.setattr(evaluate_mod, "_harness", _boom)
    result = run("summary")
    assert result.exit_code != 0
    assert "poetry install --with eval" in result.output

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from ..client import APIClient
from ..output import print_json


_INSTALL_HINT = (
    "the Helox eval harness is not installed; run 'poetry install --with eval'"
)


def _evaluation_module() -> Any:
    """Import the Helox evaluation package, or fail with an install hint."""
    try:
        import deepiri_helox_sdk.evaluation as eval_pkg
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise click.ClickException(_INSTALL_HINT) from exc
    return eval_pkg


def _harness(eval_dir: Path) -> Any:
    """Construct an AutomaticEvaluationHarness rooted at ``eval_dir``."""
    return _evaluation_module().AutomaticEvaluationHarness(eval_dir=eval_dir)


def _sdk_suite_dir() -> Path:
    """Path to the sample suites bundled with the Helox SDK."""
    return Path(_evaluation_module().__file__).parent / "suites"


def _agent_subject(client: APIClient, agent_id: str) -> Any:
    """Build a Helox ResponseGenerator that invokes a Persola agent via the API."""
    from deepiri_helox_sdk.evaluation.subjects import CallableGenerator

    def _invoke(prompt: str, max_new_tokens: int) -> str:
        payload = client.api_request(
            "POST", f"/agents/{agent_id}/invoke", json={"message": prompt}
        )
        text = payload.get("response") if isinstance(payload, dict) else None
        if text is None:
            # Returning the raw payload here would feed an API error body into
            # the grader as if the agent had said it, silently skewing scores.
            raise click.ClickException(
                f"agent {agent_id} returned no 'response' field: {payload!r}"
            )
        return str(text)

    return CallableGenerator(_invoke, name=f"agent:{agent_id}")


def _model_subject(model_path: str) -> Any:
    """Build a Helox ResponseGenerator from a local HuggingFace causal LM."""
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise click.ClickException(
            "--model requires 'transformers' (and torch) installed in this environment"
        ) from exc
    from deepiri_helox_sdk.evaluation.subjects import HFModelGenerator

    model = AutoModelForCausalLM.from_pretrained(model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    return HFModelGenerator(model, tokenizer, name=model_path)


def _load_suites(harness: Any, suite_dir: Path) -> None:
    if suite_dir.is_dir():
        harness.load_suites_from_dir(suite_dir)
    elif suite_dir.is_file():
        harness.load_test_suite(suite_dir.stem, suite_dir)
    else:
        raise click.ClickException(f"suite dir/file not found: {suite_dir}")


@click.group()
def evaluate_group() -> None:
    """Run the Helox evaluation harness against Persola agents or local models."""


@evaluate_group.command("run")
@click.option("--agent", "agent_id", default=None, help="Persola agent id to evaluate")
@click.option("--model", "model_path", default=None, help="Local HF causal LM path to evaluate")
@click.option("--suite", required=True, help="Suite name to evaluate")
@click.option(
    "--suite-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory of JSONL suites (defaults to the Helox SDK sample suites)",
)
@click.option("--max-new-tokens", default=100, type=int)
@click.option("--eval-dir", type=click.Path(path_type=Path), default=Path("evaluation"))
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def run_eval(
    ctx: click.Context,
    agent_id: str | None,
    model_path: str | None,
    suite: str,
    suite_dir: Path | None,
    max_new_tokens: int,
    eval_dir: Path,
    output_format: str,
) -> None:
    """Evaluate an agent or model against a Helox test suite."""
    if bool(agent_id) == bool(model_path):
        raise click.ClickException("provide exactly one of --agent or --model")

    client: APIClient = ctx.obj["client"]
    harness = _harness(eval_dir)
    _load_suites(harness, suite_dir or _sdk_suite_dir())
    if suite not in harness.list_suites():
        raise click.ClickException(
            f"suite {suite!r} not found; available: {harness.list_suites()}"
        )

    subject = _agent_subject(client, agent_id) if agent_id else _model_subject(model_path)  # type: ignore[arg-type]
    result = harness.evaluate_subject(subject, suite, max_new_tokens=max_new_tokens)
    if output_format == "json":
        print_json(result)
    else:
        click.echo(
            f"{result.get('suite_name')}: {result.get('passed_tests')}/"
            f"{result.get('total_tests')} passed "
            f"(avg {result.get('avg_score', 0.0):.3f}) - "
            f"{'passed' if result.get('passed') else 'failed'}"
        )


@evaluate_group.command("benchmark")
@click.option("--agent", "agent_id", required=True, help="Persola agent id to benchmark")
@click.option("--prompt", default="Write a hello world function.", show_default=True)
@click.option("--max-new-tokens", default=50, type=int)
@click.option("--runs", default=5, type=int)
@click.option("--eval-dir", type=click.Path(path_type=Path), default=Path("evaluation"))
@click.pass_context
def benchmark(
    ctx: click.Context,
    agent_id: str,
    prompt: str,
    max_new_tokens: int,
    runs: int,
    eval_dir: Path,
) -> None:
    """Benchmark generation latency/throughput for a Persola agent."""
    client: APIClient = ctx.obj["client"]
    harness = _harness(eval_dir)
    stats = harness.benchmark_subject(
        _agent_subject(client, agent_id),
        prompt,
        max_new_tokens=max_new_tokens,
        num_runs=runs,
    )
    print_json(stats)


@evaluate_group.command("summary")
@click.option("--eval-dir", type=click.Path(path_type=Path), default=Path("evaluation"))
def summary(eval_dir: Path) -> None:
    """Show aggregate evaluation history for the given eval dir."""
    print_json(_harness(eval_dir).get_evaluation_summary())


@evaluate_group.command("history")
@click.option("--suite", default=None, help="Filter history to one suite")
@click.option("--eval-dir", type=click.Path(path_type=Path), default=Path("evaluation"))
def history(suite: str | None, eval_dir: Path) -> None:
    """Show persisted evaluation history."""
    print_json(_harness(eval_dir).get_history(suite))

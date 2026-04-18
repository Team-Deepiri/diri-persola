from __future__ import annotations

import click

from .client import APIClient, CLIError
from .commands.agent import agent_group
from .commands.analyze import analyze_command
from .commands.persona import persona_group
from .commands.preset import preset_group
from .output import console, print_json, print_status_table


@click.group()
@click.option("--url", default="http://localhost:8010", show_default=True, help="Base Persola server URL.")
@click.pass_context
def cli(ctx: click.Context, url: str) -> None:
    """Persola command line interface."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = APIClient(url)
    ctx.obj["base_url"] = url.rstrip("/")


@cli.command("status")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def status_command(ctx: click.Context, output_format: str) -> None:
    client: APIClient = ctx.obj["client"]
    try:
        health = client.request("GET", "/health")
        providers = client.api_request("GET", "/provider/status")
    except CLIError as exc:
        raise click.ClickException(str(exc)) from exc
    payload = {"health": health, "providers": providers}
    if output_format == "json":
        print_json(payload)
        return
    print_status_table(health, providers)


cli.add_command(persona_group, name="persona")
cli.add_command(agent_group, name="agent")
cli.add_command(preset_group, name="preset")
cli.add_command(analyze_command, name="analyze")
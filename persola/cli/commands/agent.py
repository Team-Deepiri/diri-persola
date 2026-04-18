from __future__ import annotations

import click

from ..client import APIClient
from ..output import print_agents_table, print_json, print_single_resource


@click.group()
def agent_group() -> None:
    """Manage agents."""


@agent_group.command("list")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def list_agents(ctx: click.Context, output_format: str) -> None:
    client: APIClient = ctx.obj["client"]
    agents = client.api_request("GET", "/agents")
    if output_format == "json":
        print_json(agents)
        return
    print_agents_table(agents)


@agent_group.command("create")
@click.option("--name", required=True)
@click.option("--persona", "persona_id", default=None)
@click.option("--model", default="llama3:8b", show_default=True)
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def create_agent(ctx: click.Context, name: str, persona_id: str | None, model: str, output_format: str) -> None:
    client: APIClient = ctx.obj["client"]
    payload = {"name": name, "persona_id": persona_id, "model": model}
    agent = client.api_request("POST", "/agents", json=payload)
    print_single_resource("Agent", agent, as_json=output_format == "json")


@agent_group.command("invoke")
@click.argument("agent_id")
@click.option("--message", required=True)
@click.option("--session", "session_id", default=None)
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def invoke_agent(ctx: click.Context, agent_id: str, message: str, session_id: str | None, output_format: str) -> None:
    client: APIClient = ctx.obj["client"]
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    response = client.api_request("POST", f"/agents/{agent_id}/invoke", json=payload)
    print_single_resource("Agent Response", response, as_json=output_format == "json")
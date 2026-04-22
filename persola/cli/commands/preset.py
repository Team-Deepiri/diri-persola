from __future__ import annotations

import click

from ..client import APIClient
from ..output import print_json, print_presets_table, print_single_resource


@click.group()
def preset_group() -> None:
    """Manage presets."""


@preset_group.command("list")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def list_presets(ctx: click.Context, output_format: str) -> None:
    client: APIClient = ctx.obj["client"]
    presets = client.api_request("GET", "/presets").get("presets", {})
    if output_format == "json":
        print_json(presets)
        return
    print_presets_table(presets)


@preset_group.command("apply")
@click.argument("persona_id")
@click.argument("preset_name")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def apply_preset(ctx: click.Context, persona_id: str, preset_name: str, output_format: str) -> None:
    client: APIClient = ctx.obj["client"]
    persona = client.api_request("POST", f"/presets/{preset_name.lower()}/apply", json={"persona_id": persona_id, "preset": preset_name.lower()})
    print_single_resource("Persona", persona, as_json=output_format == "json")
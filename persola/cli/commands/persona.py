from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from ..client import APIClient, CLIError
from ..output import print_json, print_personas_table, print_single_resource


def _apply_knob_updates(payload: dict[str, Any], values: dict[str, float | None]) -> None:
    for key, value in values.items():
        if value is not None:
            payload[key] = value


def _resolve_preset(client: APIClient, preset_name: str) -> dict[str, Any]:
    presets = client.api_request("GET", "/presets").get("presets", {})
    normalized = preset_name.lower()
    if normalized in presets:
        return presets[normalized]
    for key, preset in presets.items():
        if key.lower() == normalized or str(preset.get("name", "")).lower() == normalized:
            return preset
    raise click.ClickException(f"Unknown preset: {preset_name}")


@click.group()
def persona_group() -> None:
    """Manage personas."""


@persona_group.command("list")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def list_personas(ctx: click.Context, output_format: str) -> None:
    client: APIClient = ctx.obj["client"]
    personas = client.api_request("GET", "/personas")
    if output_format == "json":
        print_json(personas)
        return
    print_personas_table(personas)


@persona_group.command("get")
@click.argument("persona_id")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def get_persona(ctx: click.Context, persona_id: str, output_format: str) -> None:
    client: APIClient = ctx.obj["client"]
    persona = client.api_request("GET", f"/personas/{persona_id}")
    print_single_resource("Persona", persona, as_json=output_format == "json")


@persona_group.command("create")
@click.option("--name", required=True)
@click.option("--description", default="")
@click.option("--preset", default=None)
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def create_persona(ctx: click.Context, name: str, description: str, preset: str | None, output_format: str) -> None:
    client: APIClient = ctx.obj["client"]
    payload: dict[str, Any] = {"name": name, "description": description}
    if preset:
        preset_payload = _resolve_preset(client, preset)
        payload.update(preset_payload.get("knobs", {}))
        payload["description"] = description or str(preset_payload.get("description", ""))
    persona = client.api_request("POST", "/personas", json=payload)
    print_single_resource("Persona", persona, as_json=output_format == "json")


@persona_group.command("update")
@click.argument("persona_id")
@click.option("--name", default=None)
@click.option("--description", default=None)
@click.option("--creativity", type=float, default=None)
@click.option("--humor", type=float, default=None)
@click.option("--formality", type=float, default=None)
@click.option("--verbosity", type=float, default=None)
@click.option("--empathy", type=float, default=None)
@click.option("--confidence", type=float, default=None)
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def update_persona(
    ctx: click.Context,
    persona_id: str,
    name: str | None,
    description: str | None,
    creativity: float | None,
    humor: float | None,
    formality: float | None,
    verbosity: float | None,
    empathy: float | None,
    confidence: float | None,
    output_format: str,
) -> None:
    client: APIClient = ctx.obj["client"]
    payload = client.api_request("GET", f"/personas/{persona_id}")
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    _apply_knob_updates(
        payload,
        {
            "creativity": creativity,
            "humor": humor,
            "formality": formality,
            "verbosity": verbosity,
            "empathy": empathy,
            "confidence": confidence,
        },
    )
    persona = client.api_request("PUT", f"/personas/{persona_id}", json=payload)
    print_single_resource("Persona", persona, as_json=output_format == "json")


@persona_group.command("delete")
@click.argument("persona_id")
@click.pass_context
def delete_persona(ctx: click.Context, persona_id: str) -> None:
    client: APIClient = ctx.obj["client"]
    client.api_request("DELETE", f"/personas/{persona_id}")
    click.echo(f"Deleted persona {persona_id}")


@persona_group.command("export")
@click.argument("persona_id")
@click.option("--out", "output_path", type=click.Path(path_type=Path), default=None)
@click.pass_context
def export_persona(ctx: click.Context, persona_id: str, output_path: Path | None) -> None:
    client: APIClient = ctx.obj["client"]
    payload = client.api_request("GET", f"/personas/{persona_id}/export")
    if output_path is not None:
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        click.echo(f"Exported persona to {output_path}")
        return
    print_json(payload)


@persona_group.command("import")
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def import_persona(ctx: click.Context, input_file: Path, output_format: str) -> None:
    client: APIClient = ctx.obj["client"]
    payload = json.loads(input_file.read_text(encoding="utf-8"))
    persona = client.api_request("POST", "/personas/import", json=payload)
    print_single_resource("Persona", persona, as_json=output_format == "json")


@persona_group.command("blend")
@click.argument("persona_a")
@click.argument("persona_b")
@click.option("--ratio", type=float, default=0.5, show_default=True)
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def blend_personas(ctx: click.Context, persona_a: str, persona_b: str, ratio: float, output_format: str) -> None:
    client: APIClient = ctx.obj["client"]
    persona = client.api_request(
        "POST",
        "/personas/blend",
        json={"persona1_id": persona_a, "persona2_id": persona_b, "ratio": ratio},
    )
    print_single_resource("Persona", persona, as_json=output_format == "json")
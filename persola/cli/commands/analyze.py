from __future__ import annotations

from pathlib import Path

import click

from ..client import APIClient
from ..output import print_json, print_single_resource


@click.command("analyze")
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option("--create", is_flag=True, default=False, help="Create a persona from the writing sample.")
@click.option("--name", default=None, help="Persona name when using --create.")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def analyze_command(ctx: click.Context, input_file: Path, create: bool, name: str | None, output_format: str) -> None:
    client: APIClient = ctx.obj["client"]
    text = input_file.read_text(encoding="utf-8")
    if create:
        payload = {"text": text, "name": name or input_file.stem}
        persona = client.api_request("POST", "/analysis/extract-and-create", json=payload)
        print_single_resource("Persona", persona, as_json=output_format == "json")
        return

    payload = {"text": text, "create_persona": False, "persona_name": name}
    result = client.api_request("POST", "/analysis/extract", json=payload)
    if output_format == "json":
        print_json(result)
        return
    print_single_resource("Analysis", result, as_json=False)
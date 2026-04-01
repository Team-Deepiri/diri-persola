from __future__ import annotations

import json
from typing import Any, Iterable

from rich.console import Console
from rich.table import Table


console = Console()


def print_json(data: Any) -> None:
    console.print_json(json.dumps(data, default=str))


def print_personas_table(personas: Iterable[dict[str, Any]]) -> None:
    table = Table(title="Personas")
    table.add_column("ID", overflow="fold")
    table.add_column("Name")
    table.add_column("Model")
    table.add_column("Preset")
    table.add_column("Updated")
    for persona in personas:
        table.add_row(
            str(persona.get("id", "")),
            str(persona.get("name", "")),
            str(persona.get("model", "")),
            "yes" if persona.get("is_preset") else "no",
            str(persona.get("updated_at", "")),
        )
    console.print(table)


def print_agents_table(agents: Iterable[dict[str, Any]]) -> None:
    table = Table(title="Agents")
    table.add_column("ID", overflow="fold")
    table.add_column("Name")
    table.add_column("Role")
    table.add_column("Model")
    table.add_column("Persona ID", overflow="fold")
    for agent in agents:
        table.add_row(
            str(agent.get("agent_id", "")),
            str(agent.get("name", "")),
            str(agent.get("role", "")),
            str(agent.get("model", "")),
            str(agent.get("persona_id", "") or "-"),
        )
    console.print(table)


def print_presets_table(presets: dict[str, dict[str, Any]]) -> None:
    table = Table(title="Presets")
    table.add_column("Key")
    table.add_column("Name")
    table.add_column("Description")
    for key, preset in presets.items():
        table.add_row(key, str(preset.get("name", "")), str(preset.get("description", "")))
    console.print(table)


def print_status_table(health: dict[str, Any], providers: dict[str, Any]) -> None:
    table = Table(title="Persola Status")
    table.add_column("Component")
    table.add_column("Status")
    table.add_column("Details")
    table.add_row("API", str(health.get("status", "unknown")), "Server health endpoint reachable")
    table.add_row("Database", "healthy" if health.get("database") else "degraded", str(health.get("database")))
    for provider in providers.get("providers", []):
        table.add_row(
            f"LLM:{provider.get('type', 'unknown')}",
            "available" if provider.get("available") else "unavailable",
            str(provider.get("model") or provider.get("base_url") or ""),
        )
    console.print(table)


def print_single_resource(title: str, data: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print_json(data)
        return
    table = Table(title=title)
    table.add_column("Field")
    table.add_column("Value", overflow="fold")
    for key, value in data.items():
        table.add_row(str(key), json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value))
    console.print(table)
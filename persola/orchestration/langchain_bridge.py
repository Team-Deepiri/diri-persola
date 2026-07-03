"""Optional LangChain bridge — uses langchain-core when installed."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

LLMFn = Callable[[str, str], Awaitable[str]]


def langchain_available() -> bool:
    try:
        import langchain_core  # noqa: F401

        return True
    except ImportError:
        return False


def build_langchain_tool_specs(registry_tools: List[Dict[str, Any]]) -> List[Any]:
    """Convert Persola tool metadata into LangChain StructuredTool instances when available."""
    if not langchain_available():
        return []
    from langchain_core.tools import StructuredTool

    specs: List[Any] = []
    for meta in registry_tools:
        name = meta["name"]
        description = meta["description"]

        async def _stub(**kwargs: Any, _name: str = name) -> str:
            return f"tool {_name} invoked with {kwargs}"

        specs.append(
            StructuredTool.from_function(
                coroutine=_stub,
                name=name,
                description=description,
            )
        )
    return specs


async def run_langchain_agent_step(
    system_prompt: str,
    user_prompt: str,
    llm_fn: LLMFn,
    tools: Optional[List[Any]] = None,
) -> str:
    """
  Fallback to direct llm_fn when LangGraph/LC agents are not configured.
  Keeps API stable for future full LangChain agent graphs.
    """
    if langchain_available() and tools:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_core.runnables import RunnableLambda

            async def _call(inputs: Dict[str, str]) -> str:
                return await llm_fn(inputs["system"], inputs["user"])

            chain = RunnableLambda(_call)
            return await chain.ainvoke({"system": system_prompt, "user": user_prompt})
        except Exception:
            pass
    return await llm_fn(system_prompt, user_prompt)

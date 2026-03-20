"""Sub-agent spawning with proper batch function-response handling."""

from __future__ import annotations

from kresearch.providers.types import ToolDeclaration

SPAWN_SUBAGENT_DECLARATION = ToolDeclaration(
    name="spawn_subagent",
    description=(
        "Spawn a focused sub-agent to research a specific sub-topic in "
        "parallel. The sub-agent runs autonomously with its own search/read "
        "loop and returns structured findings. Use when a sub-question is "
        "clearly independent and self-contained."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The specific research question for the sub-agent.",
            },
            "context": {
                "type": "string",
                "description": "Relevant context from the main research so far.",
            },
        },
        "required": ["query"],
    },
)

SUBAGENT_SYSTEM = """\
You are a focused research sub-agent for KResearch. You have a narrow task: \
investigate the given query using web_search and read_webpage, then record \
your findings with update_findings. Be thorough but efficient — you have \
limited iterations. Cite specific data, numbers, and quotes. When you have \
gathered enough, call draft_report() and write a concise summary of findings \
with inline citations [N] and a Sources list at the end."""


async def handle_spawn_subagent(args: dict, **ctx) -> dict:
    provider = ctx.get("provider")
    config = ctx.get("config")
    if not provider or not config:
        return {"error": "Provider/config not available for sub-agent."}

    from kresearch.models.state import ResearchState
    from kresearch.tools.registry import create_default_registry

    registry = create_default_registry()
    decls = [d for d in registry.get_declarations() if d.name != "spawn_subagent"]

    query = args.get("query", "")
    context = args.get("context", "")
    prompt = f"Context: {context}\n\nResearch this: {query}" if context else query

    chat = await provider.create_chat(system_instruction=SUBAGENT_SYSTEM, tools=decls)
    sub_state = ResearchState.create(query, max_iterations=5)

    response = await chat.send(prompt)
    for _ in range(5):
        if not response.function_calls:
            break
        results = []
        for fc in response.function_calls:
            result = await registry.execute(
                fc.name, fc.args, state=sub_state,
                provider=provider, config=config,
            )
            results.append((fc.name, result))
        response = await chat.send_function_responses(results)
        if sub_state.draft_requested:
            break

    findings = response.text or sub_state.mind_map.get_summary()
    return {"findings": findings, "sources_count": sub_state.mind_map.source_count()}

"""Orchestrator — the autonomous agent loop."""

from __future__ import annotations

import asyncio
import select
import sys

from kresearch.config import KResearchConfig
from kresearch.models.state import ResearchState
from kresearch.output.console import ConsoleUI
from kresearch.prompts import SYSTEM_TEMPLATE
from kresearch.providers.base import ChatSession, ProviderInterface
from kresearch.providers.types import GenerateResponse
from kresearch.tools.registry import ToolRegistry


class Orchestrator:
    """Runs the autonomous research loop."""

    def __init__(self, config: KResearchConfig, provider: ProviderInterface,
                 registry: ToolRegistry, console: ConsoleUI) -> None:
        self._config, self._provider = config, provider
        self._registry, self._console = registry, console

    async def run(self, query: str) -> str:
        state = ResearchState.create(query, self._config.max_iterations)
        input_queue: asyncio.Queue[str] = asyncio.Queue()
        chat = await self._provider.create_chat(
            system_instruction=self._build_system_prompt(state),
            tools=self._registry.get_declarations(),
        )
        self._console.start_research(query)
        input_task = asyncio.create_task(self._monitor_input(input_queue))
        try:
            return await self._agent_loop(chat, state, input_queue)
        finally:
            input_task.cancel()
            self._console.stop()

    async def _agent_loop(self, chat: ChatSession, state: ResearchState,
                          input_queue: asyncio.Queue[str]) -> str:
        response = await chat.send(f"Research this thoroughly: {state.query}")
        state.increment_iteration()
        while True:
            if not input_queue.empty():
                user_msg = await input_queue.get()
                if user_msg.lower() in ("stop", "quit", "done"):
                    self._console.log_action("draft_report", "User requested stop")
                    resp = await chat.send(
                        "[USER INTERRUPT]: Stop. Call draft_report() then write "
                        "the best report you can with current findings.")
                    return await self._finalize(resp, state, chat)
                response = await chat.send(f"[USER INTERRUPT]: {user_msg}")
            result = await self._process_response(response, state, chat)
            if result is not None:
                return result
            if state.is_over_budget():
                self._console.log_action("draft_report", "Iteration limit reached")
                resp = await chat.send(
                    "Iteration limit reached. Call draft_report() NOW and write "
                    "the final report with everything you have.")
                return await self._finalize(resp, state, chat)
            state.increment_iteration()
            self._update_ui(state)

    async def _process_response(self, response: GenerateResponse,
                                state: ResearchState, chat: ChatSession) -> str | None:
        if response.usage:
            state.token_usage.add(response.usage.input_tokens, response.usage.output_tokens)
        if not response.function_calls:
            if state.draft_requested and response.text:
                return response.text
            if response.text and len(response.text) > 500:
                return response.text
            return None
        # Execute ALL function calls, send results back in one batch
        results: list[tuple[str, dict]] = []
        for fc in response.function_calls:
            self._console.log_action(fc.name, f"{fc.name}({_short_args(fc.args)})")
            result = await self._registry.execute(
                fc.name, fc.args, state=state,
                provider=self._provider, config=self._config)
            state.log_action(fc.name, fc.args, str(result)[:200])
            results.append((fc.name, result))
        response = await chat.send_function_responses(results)
        if response.usage:
            state.token_usage.add(response.usage.input_tokens, response.usage.output_tokens)
        if state.draft_requested and response.text:
            return response.text
        if response.function_calls:
            return await self._process_response(response, state, chat)
        return None

    async def _finalize(self, response: GenerateResponse,
                        state: ResearchState, chat: ChatSession) -> str:
        for _ in range(5):
            if response.text and not response.function_calls:
                return response.text
            if response.function_calls:
                results = [(fc.name, await self._registry.execute(
                    fc.name, fc.args, state=state,
                    provider=self._provider, config=self._config))
                    for fc in response.function_calls]
                response = await chat.send_function_responses(results)
            else:
                response = await chat.send("Write the final report now.")
        return response.text or state.mind_map.get_summary()

    async def _monitor_input(self, input_queue: asyncio.Queue[str]) -> None:
        while True:
            try:
                await asyncio.sleep(0.3)
                if select.select([sys.stdin], [], [], 0)[0]:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    if line.strip():
                        await input_queue.put(line.strip())
            except (asyncio.CancelledError, Exception):
                break

    def _build_system_prompt(self, state: ResearchState) -> str:
        gaps = state.mind_map.get_gaps()
        contras = state.mind_map.get_contradictions()
        max_iter = str(state.max_iterations) if state.max_iterations else "unlimited"
        return SYSTEM_TEMPLATE.format(
            query=state.query,
            mind_map_summary=state.mind_map.get_summary() or "(no findings yet)",
            gaps=", ".join(gaps) if gaps else "none identified yet",
            contradictions=f"{len(contras)} unresolved" if contras else "none",
            source_count=state.mind_map.source_count(),
            iteration=state.iteration, max_iterations=max_iter)

    def _update_ui(self, state: ResearchState) -> None:
        self._console.update_mind_map_display(state.mind_map)
        total = state.token_usage.input_tokens + state.token_usage.output_tokens
        self._console.update_stats(state.iteration, state.mind_map.source_count(), total)


def _short_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        s = str(v)
        parts.append(f"{k}={s[:47] + '...' if len(s) > 50 else s!r}")
    return ", ".join(parts)

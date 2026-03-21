"""Orchestrator — the autonomous agent loop with full logging."""
from __future__ import annotations
import asyncio, select, sys, time
from kresearch.config import KResearchConfig
from kresearch.models.state import ResearchState
from kresearch.output.protocol import UIProtocol
from kresearch.prompts import SYSTEM_TEMPLATE
from kresearch.providers.base import ChatSession, ProviderInterface
from kresearch.providers.types import GenerateResponse
from kresearch.tools.registry import ToolRegistry


class Orchestrator:
    """Runs the autonomous research loop with detailed console output."""

    def __init__(self, config: KResearchConfig, provider: ProviderInterface,
                 registry: ToolRegistry, console: UIProtocol,
                 input_queue: asyncio.Queue[str] | None = None) -> None:
        self._config, self._provider = config, provider
        self._registry, self._console = registry, console
        self._start_time, self._external_queue = 0.0, input_queue
        self.last_state: ResearchState | None = None
    async def run(self, query: str) -> str:
        self._start_time = time.monotonic()
        state = ResearchState.create(query, self._config.max_iterations)
        input_queue = self._external_queue or asyncio.Queue()
        chat = await self._provider.create_chat(
            system_instruction=self._build_system_prompt(state),
            tools=self._registry.get_declarations(),
        )
        await self._console.start_research(query)
        input_task = None
        if self._external_queue is None:
            input_task = asyncio.create_task(self._monitor_input(input_queue))
        try:
            report = await self._agent_loop(chat, state, input_queue)
        finally:
            if input_task is not None:
                input_task.cancel()
            await self._console.stop()
        elapsed = time.monotonic() - self._start_time
        await self._console.show_total_time(elapsed, state)
        self.last_state = state
        return report

    async def _agent_loop(self, chat: ChatSession, state: ResearchState,
                          input_queue: asyncio.Queue[str]) -> str:
        await self._console.print("  💭 [dim italic]Analyzing query and planning research strategy...[/dim italic]")
        response = await self._timed_send(chat, f"Research this thoroughly: {state.query}")
        await self._log_response(response)
        state.increment_iteration()
        while True:
            if not input_queue.empty():
                user_msg = await input_queue.get()
                if user_msg.lower() in ("stop", "quit", "done"):
                    await self._console.log_action("draft_report", "User requested stop")
                    return await self._finalize(await chat.send(
                        "[USER INTERRUPT]: Stop. Write the final report now."), state, chat)
                await self._console.print(f"\n  [bold yellow]>>> User: {user_msg}[/bold yellow]\n")
                response = await self._timed_send(chat, f"[USER INTERRUPT]: {user_msg}")
                await self._log_response(response)
            result = await self._process_response(response, state, chat)
            if result is not None:
                return result
            if state.is_over_budget():
                await self._console.log_action("draft_report", "Iteration limit reached")
                return await self._finalize(await chat.send(
                    "Iteration limit. Call draft_report() NOW and write the report."), state, chat)
            state.increment_iteration()
            await self._update_ui(state)

    async def _timed_send(self, chat: ChatSession, message: str) -> GenerateResponse:
        t0 = time.monotonic()
        response = await chat.send(message)
        await self._console.print(f"  [dim]⏱  LLM response: {time.monotonic() - t0:.1f}s[/dim]")
        return response

    async def _process_response(self, response: GenerateResponse,
                                state: ResearchState, chat: ChatSession) -> str | None:
        if response.usage:
            state.token_usage.add(response.usage.input_tokens, response.usage.output_tokens)
        if not response.function_calls:
            if state.draft_requested and response.text: return response.text
            if response.text and len(response.text) > 500: return response.text
            return None
        results: list[tuple[str, dict]] = []
        for fc in response.function_calls:
            t0 = time.monotonic()
            result = await self._registry.execute(
                fc.name, fc.args, state=state, provider=self._provider, config=self._config)
            elapsed = time.monotonic() - t0
            await self._console.log_action(fc.name, f"{fc.name}({_short_args(fc.args)})", elapsed=elapsed)
            await self._console.log_result_summary(fc.name, result)
            state.log_action(fc.name, fc.args, str(result)[:200])
            results.append((fc.name, result))
        await self._console.print("  💭 [dim italic]Processing results and deciding next steps...[/dim italic]")
        t0 = time.monotonic()
        response = await chat.send_function_responses(results)
        await self._console.print(f"  [dim]⏱  LLM response: {time.monotonic() - t0:.1f}s[/dim]")
        await self._log_response(response)
        if response.usage:
            state.token_usage.add(response.usage.input_tokens, response.usage.output_tokens)
        if state.draft_requested and response.text: return response.text
        if response.function_calls: return await self._process_response(response, state, chat)
        return None

    async def _log_response(self, response: GenerateResponse) -> None:
        if response.thinking:
            await self._console.log_thinking(response.thinking)
        if response.text and not response.function_calls and len(response.text) < 500:
            await self._console.print(f"  [dim]Agent: {response.text[:300]}[/dim]")

    async def _finalize(self, resp: GenerateResponse,
                        state: ResearchState, chat: ChatSession) -> str:
        for _ in range(5):
            await self._log_response(resp)
            if resp.text and not resp.function_calls: return resp.text
            if resp.function_calls:
                results = [(fc.name, await self._registry.execute(fc.name, fc.args, state=state,
                    provider=self._provider, config=self._config)) for fc in resp.function_calls]
                resp = await chat.send_function_responses(results)
            else: resp = await chat.send("Write the final report now.")
        return resp.text or state.mind_map.get_summary()

    async def _monitor_input(self, input_queue: asyncio.Queue[str]) -> None:
        while True:
            try:
                await asyncio.sleep(0.3)
                if select.select([sys.stdin], [], [], 0)[0]:
                    line = sys.stdin.readline()
                    if not line: break
                    if line.strip(): await input_queue.put(line.strip())
            except (asyncio.CancelledError, Exception): break

    def _build_system_prompt(self, state: ResearchState) -> str:
        g, c = state.mind_map.get_gaps(), state.mind_map.get_contradictions()
        return SYSTEM_TEMPLATE.format(
            query=state.query, source_count=state.mind_map.source_count(),
            mind_map_summary=state.mind_map.get_summary() or "(no findings yet)",
            gaps=", ".join(g) if g else "none identified yet",
            contradictions=f"{len(c)} unresolved" if c else "none", iteration=state.iteration,
            max_iterations=str(state.max_iterations) if state.max_iterations else "unlimited")

    async def _update_ui(self, state: ResearchState) -> None:
        total = state.token_usage.input_tokens + state.token_usage.output_tokens
        await self._console.update_stats(state.iteration, state.mind_map.source_count(), total)


def _short_args(a: dict) -> str:
    return ", ".join(f"{k}='{str(v)[:57]}...'" if len(str(v)) > 60 else f"{k}='{v}'" for k, v in a.items())

"""Asynchronous streaming runner for the Pharma R&D & Regulatory Radar agent."""

import argparse
import asyncio
import contextlib
import itertools
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.pharma_agent.agent import root_agent

APP_NAME: str = "pharma_rd_regulatory_radar_app"
USER_ID: str = "executive_analyst_01"
SESSION_ID: str = "live_demo_session_01"

DEFAULT_PROMPT: str = (
    "Generate an executive briefing on recent approvals or clinical advances "
    "in CRISPR or gene-editing therapies by the FDA or EMA."
)

PLACEHOLDER_API_KEYS: frozenset[str] = frozenset({"your_api_key_here"})
SPINNER_FRAMES: tuple[str, ...] = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


class AsyncLoadingIndicator:
    """Non-blocking terminal spinner showing live progress while awaiting events."""

    def __init__(self, initial_message: str) -> None:
        self._message: str = initial_message
        self._is_tty: bool = sys.stdout.isatty()
        self._active: bool = False
        self._paused: bool = False
        self._task: asyncio.Task[None] | None = None
        self._start_time: float = 0.0

    def start(self) -> None:
        """Start the background spinner task."""
        if self._active:
            return
        self._active = True
        self._paused = False
        self._start_time = time.monotonic()
        if self._is_tty:
            self._task = asyncio.create_task(self._animate())
        else:
            print(f"[LOADING] {self._message}", flush=True)

    def update_message(self, message: str) -> None:
        """Update the status text displayed next to the spinner."""
        self._message = message

    def clear_line(self) -> None:
        """Clear the active spinner line before printing standard console output."""
        if self._is_tty and self._active and not self._paused:
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

    def pause(self) -> None:
        """Temporarily hide the spinner so log lines can print cleanly."""
        self.clear_line()
        self._paused = True

    def resume(self, message: str | None = None) -> None:
        """Resume spinner animation after printing an intermediate event."""
        if message:
            self._message = message
        self._paused = False

    async def stop(self) -> None:
        """Stop the background task and erase any remaining spinner characters."""
        if not self._active:
            return
        self.clear_line()
        self._active = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _animate(self) -> None:
        """Render animated Braille frames with elapsed seconds."""
        for frame in itertools.cycle(SPINNER_FRAMES):
            if not self._active:
                break
            if not self._paused:
                elapsed: float = time.monotonic() - self._start_time
                sys.stdout.write(
                    f"\r\033[K\033[36m{frame}\033[0m {self._message} ({elapsed:.1f}s)"
                )
                sys.stdout.flush()
            await asyncio.sleep(0.1)


def validate_environment(project_root: Path) -> None:
    """Load environment variables from .env and validate GenAI / Vertex AI config."""
    env_file_path: Path = project_root / ".env"
    load_dotenv(dotenv_path=env_file_path)

    use_vertex_ai: bool = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE").strip().upper() in {
        "1",
        "TRUE",
        "YES",
    }

    if use_vertex_ai:
        project_id: str = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        if not project_id or project_id == "your-gcp-project-id":
            raise EnvironmentError(
                "GOOGLE_GENAI_USE_VERTEXAI is enabled, but GOOGLE_CLOUD_PROJECT "
                "is missing or invalid in '.env'."
            )
        return

    api_key: str = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key or api_key in PLACEHOLDER_API_KEYS:
        raise EnvironmentError(
            "Missing or invalid GOOGLE_API_KEY. Copy '.env.example' to '.env' "
            "and configure a valid Google AI Studio API key before running."
        )


def parse_cli_args(argv: list[str]) -> tuple[str, bool]:
    """Parse optional prompt text and streaming mode flag."""
    parser = argparse.ArgumentParser(
        description="Run the Pharma R&D & Regulatory Radar agent programmatically."
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Optional prompt to send to the agent (defaults to CRISPR briefing).",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable real-time SSE token streaming and wait for the full response.",
    )
    args = parser.parse_args(argv)

    env_stream_enabled: bool = os.getenv("STREAM", "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }
    stream_enabled: bool = env_stream_enabled and not args.no_stream

    custom_prompt: str = " ".join(args.prompt).strip()
    resolved_prompt: str = custom_prompt if custom_prompt else DEFAULT_PROMPT
    return resolved_prompt, stream_enabled


def extract_visible_text(content: types.Content | None) -> tuple[str, bool]:
    """Extract non-thought text parts and detect whether model thought parts occurred."""
    if not content or not content.parts:
        return "", False

    text_chunks: list[str] = []
    saw_thought: bool = False

    for part in content.parts:
        if getattr(part, "thought", False):
            saw_thought = True
            continue
        if part.text:
            text_chunks.append(part.text)

    return "".join(text_chunks), saw_thought


async def run_agent_query(prompt: str, stream_enabled: bool = True) -> None:
    """Execute root_agent asynchronously with live loading status and SSE streaming."""
    session_service: InMemorySessionService = InMemorySessionService()

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    runner: Runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    user_message: types.Content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)],
    )

    run_config: RunConfig = RunConfig(
        streaming_mode=StreamingMode.SSE if stream_enabled else StreamingMode.NONE
    )

    separator: str = "=" * 80
    mode_label: str = "SSE Real-Time Stream" if stream_enabled else "Batch Response"
    model_id: str = str(getattr(root_agent.model, "model", root_agent.model))
    print(separator)
    print(f"Agent   : {root_agent.name} ({model_id})")
    print(f"Mode    : {mode_label} | Session: {SESSION_ID}")
    print(f"Prompt  : {prompt}")
    print(separator, flush=True)

    start_time: float = time.monotonic()
    has_started_streaming: bool = False
    logged_queries_pre_stream: set[str] = set()
    deferred_queries: list[str] = []
    seen_all_queries: set[str] = set()
    grounded_sources: dict[str, str] = {}

    spinner = AsyncLoadingIndicator(
        "Grounding clinical & regulatory intelligence via Google Search..."
    )
    spinner.start()

    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=user_message,
            run_config=run_config,
        ):
            function_calls = event.get_function_calls()
            if function_calls and not has_started_streaming:
                spinner.pause()
                for tool_call in function_calls:
                    print(
                        f"[TOOL CALL] Agent '{event.author}' invoked '{tool_call.name}' "
                        f"with args: {tool_call.args}",
                        flush=True,
                    )
                spinner.resume("Executing tool and synthesizing findings...")

            if event.grounding_metadata:
                if event.grounding_metadata.web_search_queries:
                    for query in event.grounding_metadata.web_search_queries:
                        if query in seen_all_queries:
                            continue
                        seen_all_queries.add(query)
                        if not has_started_streaming:
                            spinner.pause()
                            logged_queries_pre_stream.add(query)
                            print(
                                f"[TOOL CALL] Agent '{event.author}' invoked "
                                f"'google_search' -> \"{query}\"",
                                flush=True,
                            )
                            spinner.resume("Synthesizing verified FDA/EMA evidence...")
                        else:
                            deferred_queries.append(query)

                if event.grounding_metadata.grounding_chunks:
                    for chunk in event.grounding_metadata.grounding_chunks:
                        web_source = getattr(chunk, "web", None)
                        if web_source and getattr(web_source, "uri", None):
                            title: str = getattr(web_source, "title", "") or web_source.uri
                            grounded_sources[web_source.uri] = title

            chunk_text, saw_thought = extract_visible_text(event.content)
            if saw_thought and not has_started_streaming:
                spinner.update_message("Analyzing clinical & regulatory evidence...")

            if getattr(event, "partial", False) and chunk_text:
                if not has_started_streaming:
                    await spinner.stop()
                    has_started_streaming = True
                    print("\n[STREAMING RESPONSE]\n", flush=True)
                sys.stdout.write(chunk_text)
                sys.stdout.flush()
                continue

            if event.is_final_response():
                await spinner.stop()
                if has_started_streaming:
                    print("\n", flush=True)
                else:
                    print("\n[FINAL RESPONSE]\n", flush=True)
                    print(chunk_text.strip(), flush=True)
                    print("", flush=True)
    finally:
        await spinner.stop()

    if deferred_queries:
        print("[GROUNDED SEARCH QUERIES]")
        for query in deferred_queries:
            print(f"  - \"{query}\"")
        print("")

    if grounded_sources:
        print("[VERIFIED GROUNDING SOURCES]")
        for uri, title in list(grounded_sources.items())[:5]:
            print(f"  - {title}: {uri}")
        print("")

    elapsed_total: float = time.monotonic() - start_time
    total_queries: int = len(seen_all_queries)
    print(
        f"[COMPLETED] {elapsed_total:.1f}s | Search queries executed: {total_queries}"
    )
    print(separator, flush=True)


async def main() -> None:
    """Entrypoint for asynchronous programmatic execution."""
    validate_environment(project_root=PROJECT_ROOT)
    prompt, stream_enabled = parse_cli_args(sys.argv[1:])
    await run_agent_query(prompt=prompt, stream_enabled=stream_enabled)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except EnvironmentError as env_error:
        print(f"[CONFIGURATION ERROR] {env_error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Execution cancelled by user.", file=sys.stderr)
        sys.exit(130)

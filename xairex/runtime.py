"""Application runtime: state machine + engine thread + terminal interface.

Phase 2 adds the voice loop: pressing Enter (or typing ``ptt``) opens
push-to-talk - the engine records until trailing silence, transcribes locally,
asks the local Ollama brain and speaks the answer through Piper. The engine
thread is where all heavy work happens; the main thread only reads input, so
'stop' stays responsive while a request is running.

Wake word and standby listening plug into the same engine in Phase 3.
"""

from __future__ import annotations

import logging
import os
import queue
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from xairex.audio.microphone import Microphone, MicrophoneError
from xairex.audio.recorder import Recorder
from xairex.audio.resampling import TARGET_RATE, StreamResampler
from xairex.brain.conversation import Conversation
from xairex.brain.ollama_client import BrainCancelledError, BrainError, OllamaBrain
from xairex.brain.prompts import build_system_prompt, build_turbo_code_messages
from xairex.bridge.server import BridgeServer
from xairex.config import Settings
from xairex.health import run_health_checks
from xairex.memory.database import Database
from xairex.metrics import RequestMetrics
from xairex.router import classify_confirmation, route
from xairex.speech.playback import Playback, PlaybackError
from xairex.speech.synthesizer import Synthesizer, TtsError
from xairex.speech.transcriber import SttError, Transcriber
from xairex.state_machine import IllegalTransitionError, StateMachine, XairexState
from xairex.tools import ToolRegistry, ToolResult, register_default_tools
from xairex.tools.turbo_cpp import existing_project_names, pick_project_filename
from xairex.ui import Ui
from xairex import __version__

logger = logging.getLogger("xairex.runtime")

_BUSY_DETAIL = "Xairex is still working on the previous request — wait, or type 'stop'."

_STT_NOTICE = "Sorry, I did not catch that."

#: The small local model sometimes narrates an action it never performed
#: (observed 2026-10-16: "Opening youtube." with tools attached and zero tool
#: calls — nothing happened, but the user heard a success story; later the same
#: day "The volume has been set to 100%" slipped past the first version, which
#: only matched active voice). When the final reply claims an action and no tool
#: ran, one corrective round is made.
_ACTION_CLAIM_RE = re.compile(
    r"(?:"
    r"i(?:'ve| have|\s+seem\s+to\s+have|\s+think\s+i\s+have)\s+(?:now\s+|just\s+)?"
    r"(?:opened|launched|started|paused|resumed|muted|unmuted|turned|set|changed|switched|closed|put)"
    r"|have\s+(?:opened|launched|started|paused|muted|turned|set|changed)"
    r"|(?:i'm|i\s+am)\s+(?:opening|launching|turning|setting|muting|pausing|resuming|starting)"
    r"|(?:i'll|i\s+will)\s+(?:open|launch|turn|set|mute|pause|resume|close|start|switch)"
    r"|\b(?:opening|launching|muting|unmuting|pausing|resuming)\b"
    r"|\bturning\s+(?:the\s+)?volume\b"
    r"|\bsetting\s+(?:the\s+)?volume\b"
    r"|\bvolume\s+(?:is\s+now|up\s+to|at|set\s+to)\s+\d"
    r"|\bvolume\s+is\s+(?:now\s+)?(?:set\s+to|at)\s+\d"
    r"|\bvolume\s+(?:has\s+been|was|is\s+now)\s+"
    r"(?:set|changed|turned|raised|lowered|adjusted|muted|unmuted|increased|decreased)\b"
    r"|\b(?:sound|audio|playback|music|media)\s+(?:has\s+been|was|is\s+now)\s+"
    r"(?:set|changed|turned|muted|unmuted|raised|lowered|paused|resumed)\b"
    r"|\b(?:wi-?fi|wireless|bluetooth)\s+(?:has\s+been|was|is\s+now)\s+"
    r"(?:turned|switched|set|disabled|enabled|connected|disconnected)\b"
    r"|\b(?:app|application|browser|page|window|site|website|file|notepad|chrome|edge|firefox|calculator)"
    r"\s+has\s+been\s+(?:opened|launched|closed|started|switched)\b"
    r"|^\s*it\s+(?:has\s+been|is\s+now)\s+"
    r"(?:set|changed|opened|launched|muted|unmuted|paused|resumed|closed|started|switched|turned|at\s+\d)"
    r")",
    re.IGNORECASE,
)

_ACTION_CORRECTION_PROMPT = (
    "Correction: your last message described performing an action, but no tool call was made, "
    "so nothing actually happened. If the user asked you to do something, call the correct tool now. "
    "If you cannot do it, say so plainly. Never claim an action you did not perform."
)


def _claims_action(text: str) -> bool:
    """Heuristic: does *text* narrate an action that only a tool could perform?"""
    return bool(_ACTION_CLAIM_RE.search(text or ""))


#: The model sometimes ends a tool-using turn with no words at all (live
#: 2026-10-16: four tool calls, 60 s, empty reply -> the old dead-end "I did
#: not manage to produce an answer for that."). One plain-text round is
#: requested first; if even that stays empty, Xairex asks instead of stalling
#: (owner's standing rule: when you cannot get clarity, ask).
_REPLY_REQUIRED_PROMPT = (
    "You already used tools for this request, but your reply was empty. Now answer the user in plain "
    "text in one or two short sentences: say what actually happened (from the tool results above) and "
    "what you did or could not do. Do not call any tools."
)

_EMPTY_NO_ANSWER = "I could not work that one out — tell me again in a few words and I will get it right."
_EMPTY_WITH_TOOLS = (
    "I did what I could above, but I could not put it into words — ask me again a little more precisely."
)

_CODE_FENCE_LINE_RE = re.compile(r"^\s*```[A-Za-z0-9+#._-]*\s*$")


def _strip_code_fences(text: str) -> str:
    """Drop the markdown code fence a model may wrap a generated program in."""
    if "```" not in text:
        return text.strip("\n")
    kept = [line for line in text.splitlines() if not _CODE_FENCE_LINE_RE.match(line)]
    return "\n".join(kept).strip("\n")


@dataclass
class _Job:
    kind: str  # "ask" | "say" | "ptt"
    text: str = ""


class Runtime:
    """Owns the state machine, worker thread and user-facing commands."""

    def __init__(
        self,
        settings: Settings,
        *,
        brain: OllamaBrain | None = None,
        synthesizer: Synthesizer | None = None,
        playback: Playback | None = None,
        microphone: Microphone | None = None,
        transcriber: Transcriber | None = None,
        ui: Ui | None = None,
        tools: ToolRegistry | None = None,
        on_state: Callable[[XairexState, XairexState], None] | None = None,
    ) -> None:
        self.settings = settings
        self._brain = brain
        self._synthesizer = synthesizer
        self._playback = playback
        self._microphone = microphone
        self._transcriber = transcriber
        self._resampler: StreamResampler | None = None
        self._ui = ui if ui is not None else Ui.from_settings(settings)
        self._external_on_state = on_state

        self._cancel = threading.Event()
        self._shutdown = threading.Event()
        self._jobs: queue.Queue[_Job | None] = queue.Queue(maxsize=16)
        self._engine_thread: threading.Thread | None = None
        self._resource_lock = threading.RLock()  # guards lazy model/resource creation
        self._warmup_thread: threading.Thread | None = None

        self.state = StateMachine(initial=XairexState.STARTING, on_change=self._state_changed)
        
        # Database for memory (G14 - persistent memory, no amnesia)
        self.db = Database(settings.resolve_path(settings.memory.database_path)) if settings.memory.enabled else None
        if self.db:
            self.db.connect()
        
        # Build system prompt with profile facts (G14)
        profile_facts = self.db.all_profile_facts() if self.db else {}
        system_prompt = build_system_prompt(settings, profile_facts)
        
        # Conversation with optional persistence (G14)
        self.conversation = Conversation(
            system_prompt=system_prompt,
            history_limit=settings.brain.history_limit,
            db=self.db,
            persist=settings.memory.store_conversation if self.db else False,
        )
        self._tts_ok = True
        # G11: a previewed organize plan waits here for a bare yes/no. One-shot:
        # any unrelated ask supersedes it (see _answer).
        self._pending_organize: dict[str, Any] | None = None

        self._tool_db: Database | None = None
        # The bridge object exists from the start (tools hold a reference); the
        # loopback listener opens in start_engine().
        self.bridge = BridgeServer(settings)
        self.tools = tools if tools is not None else self._build_tools()

    # ------------------------------------------------------------------ tools

    def _build_tools(self) -> ToolRegistry:
        registry = ToolRegistry(audit=self._tool_audit)
        register_default_tools(registry, self.settings, bridge=self.bridge, db=self.db)
        registry.disable(*self.settings.tools.disabled)
        return registry

    def _tool_audit(self, name: str, arguments: dict[str, Any], result: ToolResult, duration: float) -> None:
        """Audit hook: one ``tool_runs`` row per executed tool call."""
        if not self.settings.memory.enabled:
            return
        if self._tool_db is None:
            self._tool_db = Database(self.settings.resolve_path(self.settings.memory.database_path))
        self._tool_db.log_tool_run(
            tool=name,
            arguments=arguments,
            ok=result.ok,
            message=result.message,
            duration_ms=duration * 1000.0,
        )

    # ------------------------------------------------------------ resources

    def _get_brain(self) -> OllamaBrain:
        with self._resource_lock:
            if self._brain is None:
                self._brain = OllamaBrain.from_settings(self.settings)
            return self._brain

    def _get_synthesizer(self) -> Synthesizer:
        with self._resource_lock:
            if self._synthesizer is None:
                self._synthesizer = Synthesizer.from_settings(self.settings)
            return self._synthesizer

    def _get_playback(self) -> Playback:
        with self._resource_lock:
            if self._playback is None:
                self._playback = Playback.from_settings(self.settings)
            return self._playback

    def _get_transcriber(self) -> Transcriber:
        with self._resource_lock:
            if self._transcriber is None:
                self._transcriber = Transcriber.from_settings(self.settings)
            return self._transcriber

    def _get_microphone(self) -> Microphone | None:
        """Open the capture stream once per session; ``None`` when unavailable."""
        if self._microphone is None:
            try:
                candidate = Microphone.from_settings(self.settings)
                candidate.open()
            except MicrophoneError as exc:
                self._ui.print_tag("mic", str(exc), "red")
                self._ui.print_tag("mic", "Push-to-talk is unavailable; typed 'ask' still works.")
                return None
            self._microphone = candidate
            # Let stream-open transients (pops/clicks) land in the queue, so the
            # next capture's drain can discard them (measured; see D18).
            time.sleep(0.35)
        if self._resampler is None:
            self._resampler = StreamResampler(self._microphone.device_rate, TARGET_RATE)
        return self._microphone

    # ------------------------------------------------------------ lifecycle

    def prepare(self) -> None:
        """Preflight shared by the terminal and GUI front ends.

        Prints the banner and health report, records whether TTS/brain are
        usable, opens the capture stream and parks the machine in ``IDLE``.
        """
        self._ui.print_banner()

        report = run_health_checks(self.settings, brain=self._brain)
        self._ui.print_report(report.render())

        voice = self.settings.resolve_path(self.settings.tts.voice_path)
        self._tts_ok = voice.is_file() and (voice.parent / (voice.name + ".json")).is_file()
        ollama_check = next((c for c in report.checks if c.name == "ollama"), None)
        brain_ok = bool(ollama_check and ollama_check.ok)

        if not self._tts_ok:
            self._ui.print_warn("Piper voice files are missing - answers will be text-only until models are prepared.")
        if not brain_ok:
            self._ui.print_warn(
                "Ollama or the local model is not ready - 'ask' will fail until it is (see checks above)."
            )

        self._get_microphone()  # opens the capture stream; prints a hint when unavailable
        self.state.transition(XairexState.IDLE)

    def start_engine(self) -> None:
        """Start the worker thread and the browser bridge (idempotent)."""
        if self._engine_thread is not None and self._engine_thread.is_alive():
            return
        self._engine_thread = threading.Thread(target=self._engine_loop, name="xairex-engine", daemon=True)
        self._engine_thread.start()
        self._start_bridge()

    def _start_bridge(self) -> None:
        """Bring the loopback browser bridge up; a busy port is non-fatal."""
        if not self.settings.bridge.enabled:
            logger.debug("browser bridge disabled in settings")
            return
        if self.bridge.start():
            logger.info("browser bridge listening on 127.0.0.1:%s", self.bridge.port)
        elif getattr(self.bridge, "refused_reason", None) == "already-served":
            self._ui.print_warn(
                f"Another Xairex window is already serving the browser bridge on "
                f"127.0.0.1:{self.settings.bridge.port} — this window runs without it; "
                "browser notes and controls stay with the other window."
            )
        else:
            self._ui.print_warn(
                f"Browser bridge could not listen on 127.0.0.1:{self.settings.bridge.port} "
                "(port busy?) — browser tools will report it as off."
            )

    def warm_up(self, *, background: bool = True) -> threading.Thread | None:
        """Preload whisper/piper/ollama so the first real request is fast.

        Without this, the first spoken/typed request of a session pays the
        model-load costs inside the user-visible request (observed 2026-10-16:
        27 s for the first spoken command — Ollama cold load ~15 s, Piper ~4 s).
        Warm-up is best-effort: every failure is logged and ignored, and the
        lazy loaders simply try again on first use.
        """
        if self._warmup_thread is not None and self._warmup_thread.is_alive():
            return self._warmup_thread
        if not background:
            self._run_warmup()
            return None
        thread = threading.Thread(target=self._run_warmup, name="xairex-warmup", daemon=True)
        thread.start()
        self._warmup_thread = thread
        return thread

    def _run_warmup(self) -> None:
        started = time.monotonic()
        self._ui.print_muted("warming up local models (whisper, piper, ollama) in the background…")
        steps = (("whisper", self._warm_stt), ("piper", self._warm_tts), ("ollama", self._warm_brain))
        for name, step in steps:
            if self._shutdown.is_set():
                return
            try:
                step()
            except Exception:
                logger.debug("Warm-up step '%s' skipped", name, exc_info=True)
        logger.info("Warm-up finished in %.1f s", time.monotonic() - started)

    def _warm_stt(self) -> None:
        self._get_transcriber().load()

    def _warm_tts(self) -> None:
        if self._tts_ok:
            self._get_synthesizer().say("Ready.")  # audio discarded: loads the voice + first synth

    def _warm_brain(self) -> None:
        self._get_brain().chat([{"role": "user", "content": "Reply with the single word: ready."}])

    def run(self) -> int:
        """Start the engine, print the preflight report and serve the terminal."""
        self.prepare()
        self.start_engine()
        self.warm_up()
        self._ui.print_plain(self._ui.help_block())
        try:
            while not self._shutdown.is_set():
                try:
                    line = input(self._ui.prompt())
                except (EOFError, KeyboardInterrupt):
                    self._ui.newline()
                    break
                if not self._handle_input(line):
                    break
        finally:
            self.shutdown()
        return 0

    def shutdown(self) -> None:
        """Stop the engine and release resources. Idempotent."""
        if self.state.state is not XairexState.STOPPING:
            try:
                self.state.transition(XairexState.STOPPING)
            except IllegalTransitionError:  # pragma: no cover - defensive
                pass
        self._shutdown.set()
        self.cancel_current()
        try:
            self._jobs.put_nowait(None)
        except queue.Full:  # pragma: no cover - defensive
            pass
        if self._engine_thread is not None:
            self._engine_thread.join(timeout=3.0)
        if self._microphone is not None:
            self._microphone.close()
        if self._playback is not None:
            self._playback.close()
        if self._brain is not None:
            self._brain.close()
        if self._tool_db is not None:
            self._tool_db.close()
        # Close memory database (G14)
        if self.db is not None:
            try:
                self.db.close()
            except Exception:
                pass
        self.bridge.stop()
        self._ui.print_muted("Goodbye.")

    # ------------------------------------------------------------ input side

    def _handle_input(self, line: str) -> bool:
        """Handle one terminal line. Returns False to quit."""
        line = line.strip()
        if not line:
            # Push-to-talk: an empty line starts a voice capture.
            self.submit_ptt()
            return True
        command, _, rest = line.partition(" ")
        command = command.lower()
        rest = rest.strip()

        if command in ("quit", "exit"):
            return False
        if command == "help":
            self._ui.print_plain(self._ui.help_block())
            return True
        if command == "stop":
            self.cancel_current()
            self._ui.print_muted("[stopped]")
            return True
        if command == "health":
            self._ui.print_report(self.health_report_text())
            return True
        if command == "ask":
            if not rest:
                self._ui.print_error("usage: ask <text>")
                return True
            self.submit_ask(rest)
            return True
        if command == "say":
            if not rest:
                self._ui.print_error("usage: say <text>")
                return True
            self.submit_say(rest)
            return True
        if command == "ptt":
            self.submit_ptt()
            return True

        # A bare sentence: treat it as a question (friendlier terminal UX).
        self.submit_ask(line)
        return True

    def submit_ask(self, text: str) -> None:
        """Queue a typed question (used by the GUI; the CLI has ``ask``)."""
        self._enqueue(_Job("ask", text))

    def submit_say(self, text: str) -> None:
        """Queue text to speak without consulting the model."""
        self._enqueue(_Job("say", text))

    def submit_ptt(self) -> None:
        """Queue one push-to-talk capture."""
        self._enqueue(_Job("ptt"))

    def health_report_text(self) -> str:
        """Render the offline readiness report (CLI ``health`` and the GUI)."""
        return run_health_checks(self.settings, brain=self._brain).render()

    def _enqueue(self, job: _Job) -> None:
        try:
            self._jobs.put_nowait(job)
        except queue.Full:
            self._ui.print_busy(_BUSY_DETAIL)

    def cancel_current(self) -> None:
        """Signal the running request to stop (playback included)."""
        self._cancel.set()
        if self._playback is not None:
            self._playback.stop()

    def _state_changed(self, frm: XairexState, to: XairexState) -> None:
        logger.debug("state: %s -> %s", frm.value, to.value)
        if self._external_on_state is not None:
            try:
                self._external_on_state(frm, to)
            except Exception:  # pragma: no cover - UI callbacks must never crash the engine
                logger.exception("on_state callback failed (%s -> %s)", frm.value, to.value)

    # ----------------------------------------------------------- engine side

    def _engine_loop(self) -> None:
        while not self._shutdown.is_set():
            try:
                job = self._jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            if job is None:
                break
            try:
                if job.kind == "ask":
                    self._handle_ask(job.text)
                elif job.kind == "say":
                    self._handle_say(job.text)
                elif job.kind == "ptt":
                    self._handle_ptt()
            except Exception:  # pragma: no cover - last-resort guard
                logger.exception("Unhandled error while processing a request")
                self._safe_error_state()
                self._ui.print_error("Something went wrong while processing that request; see the log for details.")

    def _safe_error_state(self) -> None:
        try:
            self.state.transition(XairexState.ERROR)
            self.state.transition(XairexState.IDLE)
        except IllegalTransitionError:  # pragma: no cover - defensive
            logger.error("Could not return to IDLE after an error (state=%s)", self.state.state.value)

    def _to_idle(self) -> None:
        """Return to IDLE unless the runtime is stopping (shutdown race guard).

        A job can finish after STOPPING was entered (app closing mid-request),
        where IDLE is an illegal transition; that used to surface as an ERROR
        log line plus a failed recovery on shutdown.
        """
        if self.state.state is XairexState.STOPPING:
            return
        try:
            self.state.transition(XairexState.IDLE)
        except IllegalTransitionError:  # pragma: no cover - defensive
            logger.debug("IDLE transition skipped (state=%s)", self.state.state.value)

    def _handle_ask(self, text: str) -> None:
        self._cancel.clear()
        self._answer(text, RequestMetrics(label="ask"))

    def _answer(self, text: str, metrics: RequestMetrics) -> None:
        """Route *text*: fast deterministic commands first, the LLM otherwise."""
        pending = self._pending_organize
        if pending is not None:
            # A preview was shown and we asked "shall I do it?" — a bare yes
            # applies it, a no cancels, and any other ask supersedes it.
            verdict = classify_confirmation(text)
            self._pending_organize = None
            if verdict == "yes":
                self._run_tool_command(
                    text, "organize_folder", {"action": "apply", "folder": pending["folder"]}, metrics
                )
                return
            if verdict == "no":
                self._finish_answer(text, "Okay — I left everything where it is.", metrics)
                return

        routed = route(text, self.settings)
        if routed is not None:
            if routed.tool == "code_task":
                self._answer_code_task(text, routed.arguments, metrics)
            else:
                self._run_tool_command(text, routed.tool, routed.arguments, metrics)
            return

        self.state.transition(XairexState.THINKING)
        tool_specs = self.tools.ollama_tools()
        messages = self.conversation.build(text)
        corrected = False
        used = 0
        try:
            with self._ui.spinner("thinking", "local neural pass"):
                reply = self._get_brain().chat(messages, tools=tool_specs or None, cancel_event=self._cancel)
                rounds = max(0, int(self.settings.brain.max_tool_rounds))
                while True:
                    while reply.tool_calls:
                        if used >= rounds:
                            # Round budget spent: force a text answer without tools.
                            reply = self._get_brain().chat(messages, tools=None, cancel_event=self._cancel)
                            break
                        used += 1
                        messages.append(
                            {
                                "role": "assistant",
                                "content": reply.content or "",
                                "tool_calls": [
                                    {"function": {"name": call.name, "arguments": call.arguments}}
                                    for call in reply.tool_calls
                                ],
                            }
                        )
                        for call in reply.tool_calls:
                            if self._cancel.is_set():
                                raise BrainCancelledError("Request stopped.")
                            self.state.transition(XairexState.EXECUTING_TOOL)
                            result = self.tools.execute(call.name, call.arguments)
                            self._note_organize_result(call.name, result)
                            self.state.transition(XairexState.THINKING)
                            self._ui.print_tag(
                                "tool", f"{call.name}: {result.message}", "green" if result.ok else "yellow"
                            )
                            messages.append({"role": "tool", "tool_name": call.name, "content": result.message})
                        reply = self._get_brain().chat(messages, tools=tool_specs or None, cancel_event=self._cancel)

                    if corrected or used > 0 or not _claims_action(reply.content):
                        break
                    # The model narrated an action it never performed. One
                    # corrective round: it either calls the tool now or must
                    # admit it cannot (never speak a fake success).
                    corrected = True
                    messages.append({"role": "assistant", "content": reply.content or ""})
                    messages.append({"role": "system", "content": _ACTION_CORRECTION_PROMPT})
                    reply = self._get_brain().chat(messages, tools=tool_specs or None, cancel_event=self._cancel)
        except BrainCancelledError:
            self._ui.print_muted("[stopped]")
            self._to_idle()
            return
        except BrainError as exc:
            self._ui.print_error(str(exc))
            self._to_idle()
            return
        metrics.mark("llm")

        content = reply.content.strip()
        if corrected and used == 0 and _claims_action(content):
            content = "I could not perform that action — nothing was changed."
        if not content:
            # No words after the tool work: one plain-text summarize round,
            # then a clarifying ask — never the old dead-end sentence.
            messages.append({"role": "system", "content": _REPLY_REQUIRED_PROMPT})
            try:
                with self._ui.spinner("putting it into words", "local neural pass"):
                    retry = self._get_brain().chat(messages, tools=None, cancel_event=self._cancel)
                content = (retry.content or "").strip()
                metrics.mark("llm")
            except BrainCancelledError:
                self._ui.print_muted("[stopped]")
                self._to_idle()
                return
            except BrainError as exc:
                logger.debug("Summarize round failed: %s", exc)
        if not content:
            content = _EMPTY_WITH_TOOLS if used > 0 else _EMPTY_NO_ANSWER
        self.conversation.commit(text, content)
        self._ui.print_answer(content)

        if self._tts_ok and not self._cancel.is_set():
            self._speak(content, metrics)
        else:
            self._to_idle()
        logger.info(metrics.summary())
        self._ui.print_muted(metrics.summary())

    def _answer_code_task(self, user_text: str, arguments: dict[str, Any], metrics: RequestMetrics) -> None:
        """Tier-1 code asks (G24): focused generation, then the purpose-built tool.

        Measured live 2026-10-16: handed the general prompt, the small model
        planned the owner's compound ask with raw keystroke tools, typed the
        program twice, mixed in an unrelated website, wrote modern C++ that the
        Borland compiler cannot build, and ended with no answer at all after
        60 s. So the runtime does the part the model is good at (writing one
        program from a tight dialect-locked prompt) and skips the part it is bad
        at (choosing a strategy out of twenty tool schemas).
        """
        request = str(arguments.get("request") or user_text).strip() or user_text
        self.state.transition(XairexState.THINKING)
        try:
            with self._ui.spinner("writing the program", "local neural pass"):
                code = self._generate_code(request)
        except BrainCancelledError:
            self._ui.print_muted("[stopped]")
            self._to_idle()
            return
        except BrainError as exc:
            self._ui.print_error(str(exc))
            self._to_idle()
            return
        metrics.mark("llm")

        if not code.strip():
            self._finish_answer(
                user_text,
                "I couldn't work out what the program should do from that. Tell me in one line what it "
                "should do and I'll write it into Turbo C++.",
                metrics,
            )
            return

        filename = pick_project_filename(request, existing_project_names())
        self.state.transition(XairexState.EXECUTING_TOOL)
        self._ui.print_tag("tool", f"turbo_write_code(filename={filename}, {len(code.splitlines())} lines of code)")
        result = self.tools.execute("turbo_write_code", {"code": code, "filename": filename})
        metrics.mark("tool")
        self._finish_answer(user_text, result.message, metrics)

    def _generate_code(self, request: str) -> str:
        """One focused generation pass (no tools) — returns clean program text."""
        messages = build_turbo_code_messages(request)
        reply = self._get_brain().chat(messages, tools=None, cancel_event=self._cancel)
        return _strip_code_fences(reply.content or "")

    def _finish_answer(self, user_text: str, message: str, metrics: RequestMetrics) -> None:
        """Commit, print and speak the final message of a deterministic flow."""
        self.conversation.commit(user_text, message)
        self._ui.print_answer(message)
        if self._tts_ok and not self._cancel.is_set():
            self._speak(message, metrics)
        else:
            self._to_idle()
        logger.info(metrics.summary())
        self._ui.print_muted(metrics.summary())

    def _note_organize_result(self, tool: str, result: ToolResult) -> None:
        """Remember a pending organize preview so a bare "yes" can apply it.

        Fed from both execution paths (routed commands and LLM tool calls), so
        a preview shown by either one arms the yes/no gate exactly once.
        """
        if tool != "organize_folder" or not isinstance(result.data, dict):
            return
        action = result.data.get("action")
        if action == "preview" and result.ok and int(result.data.get("total", 0) or 0) > 0:
            self._pending_organize = {"folder": str(result.data.get("folder", ""))}
        elif action == "apply":
            self._pending_organize = None

    def _run_tool_command(self, user_text: str, tool: str, arguments: dict[str, Any], metrics: RequestMetrics) -> None:
        """Execute one routed tool call, speak its confirmation, audit it."""
        self.state.transition(XairexState.EXECUTING_TOOL)
        detail = ", ".join(f"{key}={value}" for key, value in arguments.items())
        self._ui.print_tag("tool", f"{tool}({detail})")
        result = self.tools.execute(tool, arguments)
        self._note_organize_result(tool, result)
        metrics.mark("tool")

        self.conversation.commit(user_text, result.message)
        self._ui.print_answer(result.message)

        fallback = result.data.get("open") if isinstance(result.data, dict) else None
        if isinstance(fallback, str) and fallback:
            try:
                os.startfile(fallback)  # type: ignore[attr-defined]
            except OSError:
                logger.debug("Could not open fallback target %s", fallback, exc_info=True)

        if self._tts_ok and not self._cancel.is_set():
            self._speak(result.message, metrics)
        else:
            self._to_idle()
        logger.info(metrics.summary())
        self._ui.print_muted(metrics.summary())

    # ----------------------------------------------------------------- voice

    def _handle_ptt(self) -> None:
        """Push-to-talk: record one spoken question, transcribe it and answer."""
        self._cancel.clear()
        microphone = self._get_microphone()
        if microphone is None:
            return  # a friendly message was already printed
        metrics = RequestMetrics(label="ptt")
        recorder = Recorder.from_settings(self.settings)

        self._ui.listening_banner()
        self.state.transition(XairexState.RECORDING_COMMAND)
        utterance = self._record_command(microphone, recorder)
        metrics.mark("record")

        if utterance is None or len(utterance) == 0:
            if self._cancel.is_set():
                self._ui.print_muted("[stopped]")
            else:
                self._ui.print_tag("ptt", "I did not hear any speech.")
            self._to_idle()
            return

        self.state.transition(XairexState.TRANSCRIBING)
        try:
            with self._ui.spinner("transcribing", "whisper (local)"):
                text = self._get_transcriber().transcribe(utterance, self._cancel)
        except SttError as exc:
            self._ui.print_tag("stt", str(exc), "red")
            self._to_idle()
            return
        metrics.mark("stt")

        if text is None:
            self._to_idle()
            if self._cancel.is_set():
                self._ui.print_muted("[stopped]")
            else:
                self._ui.print_tag("ptt", "I did not catch that.")
                if self._tts_ok:
                    self._speak(_STT_NOTICE, None)
            return

        self._ui.print_user_echo(text)
        self._answer(text, metrics)

    def _record_command(self, microphone: Microphone, recorder: Recorder) -> np.ndarray | None:
        """Drive capture until the recorder yields an utterance.

        Returns int16 audio, or ``None`` when the wait bound expires, the user
        cancels or the assistant is shutting down.
        """
        assert self._resampler is not None  # set by _get_microphone
        microphone.drain()  # drop stale audio captured while Xairex was busy
        meter = self._ui.listening_meter()
        started = time.monotonic()
        wait_bound = self._ptt_wait_seconds()
        no_speech_deadline = started + wait_bound
        hard_stop = started + wait_bound * 2 + 1.0
        try:
            while True:
                if self._shutdown.is_set():
                    recorder.cancel()
                    return None
                if self._cancel.is_set():
                    recorder.cancel()
                    return None
                frame = microphone.read_frame(timeout=0.2)
                if frame is None:
                    if time.monotonic() > hard_stop:
                        return recorder.flush() if recorder.is_recording else None
                    if not recorder.is_recording and time.monotonic() > no_speech_deadline:
                        return None
                    continue
                pcm16 = self._resampler.process(frame)
                meter.update(pcm16)
                utterance = recorder.feed(pcm16)
                if utterance is not None:
                    return utterance
                if not recorder.is_recording and time.monotonic() > no_speech_deadline:
                    return None
        finally:
            meter.finish()

    def _ptt_wait_seconds(self) -> float:
        """Upper bound for waiting on speech to start (test seam).

        The recorder separately caps the capture itself; this only governs how
        long 'listening...' waits before reporting that nothing was heard.
        """
        return min(8.0, self.settings.audio.max_record_seconds)

    def _handle_say(self, text: str) -> None:
        self._cancel.clear()
        if not self._tts_ok:
            self._ui.print_answer(f"{text}  (text-only: Piper voice not ready)")
            return
        self._speak(text, None)

    def _speak(self, text: str, metrics: RequestMetrics | None) -> None:
        """Synthesize and play *text*, then return to IDLE."""
        self.state.transition(XairexState.SPEAKING)
        try:
            with self._ui.spinner("synthesizing", "piper voice"):
                pcm = self._get_synthesizer().say(text)
        except TtsError as exc:
            self._ui.print_tag("tts", str(exc), "red")
            self._to_idle()
            return
        if metrics is not None:
            metrics.mark("tts")
        if pcm.data and not self._cancel.is_set():
            try:
                with self._ui.spinner("speaking", "voice stream", frames="wave"):
                    self._get_playback().play(pcm, self._cancel)
            except PlaybackError as exc:
                self._ui.print_tag("audio", str(exc), "red")
        if metrics is not None:
            metrics.mark("played")
        self._to_idle()

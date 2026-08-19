from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from app.core.command_profiles import CommandProfile, OutputParserConfig
from app.core.enums import OperationAction, TargetStatus
from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult
from app.executors.command_builders import CommandProfileNotConfigured, ServicesCommandBuilder
from app.executors.command_builders.services_command import UnknownCommandProfile
from app.parsers import (
    JsonStatusParser,
    LegacyTextStatusParser,
    RawOutputParser,
    StatusOutputParser,
)
from app.parsers.configurable import build_status_parser
from app.parsers.status_result import redact_sensitive_output

_FIXTURE_SCRIPT = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "fake_services.sh"
).resolve()
_ALLOWED_ENVIRONMENT_KEYS = {
    "HOME",
    "PATH",
    "LANG",
    "LC_ALL",
    "ANSIBLE_CONFIG",
    "SSH_AUTH_SOCK",
    "OPSPILOT_SSH_HOST",
    "OPSPILOT_SSH_PORT",
    "OPSPILOT_SSH_USER",
    "OPSPILOT_SSH_PRIVATE_KEY_PATH",
    "OPSPILOT_SSH_KNOWN_HOSTS_PATH",
    "OPSPILOT_REMOTE_SERVICES_SCRIPT",
    "OPSPILOT_REMOTE_WORKING_DIRECTORY",
    "OPSPILOT_SSH_CONNECT_TIMEOUT_SECONDS",
}


@dataclass(frozen=True)
class LocalServicesExecutorConfig:
    script_path: str | None
    working_directory: str | None
    command_profile: str = "pending-confirmation"
    output_parser: str = "raw_output"
    timeout_seconds: int = 60
    allowed_environments: frozenset[str] = frozenset()
    allowed_hosts: frozenset[str] = frozenset()
    allowed_services: frozenset[str] = frozenset()
    allowed_actions: frozenset[str] = frozenset({"status"})
    command_profiles: dict[str, CommandProfile] = field(default_factory=dict)
    output_parsers: dict[str, OutputParserConfig] = field(default_factory=dict)
    process_environment: dict[str, str] = field(default_factory=dict)
    max_output_bytes: int = 262_144
    termination_grace_seconds: float = 2.0


class LocalServicesExecutor(BaseExecutor):
    executor_type = "local_services"
    supported_actions = frozenset(
        {OperationAction.STATUS, OperationAction.START, OperationAction.STOP}
    )

    def __init__(
        self,
        config: LocalServicesExecutorConfig,
        parser: StatusOutputParser | None = None,
    ) -> None:
        self.config = config
        self._builder = ServicesCommandBuilder(
            script_path=config.script_path or "",
            command_profile=config.command_profile,
            profiles=config.command_profiles,
        )
        self.parser = parser or self._build_bound_parser()
        self._processes: dict[str, set[subprocess.Popen[bytes]]] = {}
        self._cancelled: set[str] = set()
        self._process_lock = threading.Lock()

    @property
    def capabilities(self) -> frozenset[OperationAction]:
        try:
            return self._builder.capabilities
        except (CommandProfileNotConfigured, UnknownCommandProfile, ValueError):
            return frozenset()

    def validate_configuration(self) -> None:
        self._validate_paths()
        self._validate_process_environment()
        self._builder.validate()
        self._build_bound_parser()

    def cancel(self, task_id: str) -> bool:
        with self._process_lock:
            processes = tuple(self._processes.get(task_id, ()))
        live = [process for process in processes if process.poll() is None]
        if not live:
            return False
        with self._process_lock:
            self._cancelled.add(task_id)
        for process in live:
            self._terminate_process_group(process, signal.SIGTERM)
        return True

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        target_summary = f"{request.environment_code}/{request.host_name}/{request.service_name}"
        try:
            _, working_directory = self._validate_paths()
            self._validate_process_environment()
            argv = self._builder.build(request)
            self._validate_request(request)
        except (CommandProfileNotConfigured, UnknownCommandProfile) as exc:
            code = (
                "EXECUTION_REQUEST_REJECTED"
                if self.config.command_profile == "test-fixture-v1"
                and request.action is not OperationAction.STATUS
                else "COMMAND_PROFILE_NOT_CONFIGURED"
            )
            return self._failure(str(exc), code, target_summary, exit_code=78)
        except ValueError as exc:
            return self._failure(str(exc), "EXECUTION_REQUEST_REJECTED", target_summary)

        started = time.monotonic()
        process: subprocess.Popen[bytes] | None = None
        task_key = request.task_id or f"anonymous:{id(request)}"
        try:
            process_environment = {
                "PATH": "/usr/bin:/bin",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                **self.config.process_environment,
            }
            process = subprocess.Popen(
                argv,
                shell=False,
                cwd=working_directory,
                env=process_environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                start_new_session=True,
                close_fds=True,
            )
            with self._process_lock:
                self._processes.setdefault(task_key, set()).add(process)
            stdout_bytes, stderr_bytes, timed_out, cancelled = self._communicate_capped(
                process,
                min(request.timeout_seconds, self.config.timeout_seconds),
                task_key,
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            stdout = redact_sensitive_output(stdout)
            stderr = redact_sensitive_output(stderr)
            if timed_out or cancelled:
                return ExecutionResult(
                    status=TargetStatus.CANCELLED if cancelled else TargetStatus.TIMED_OUT,
                    output=stdout or None,
                    error_message=stderr
                    or ("services.sh cancelled" if cancelled else "services.sh timed out"),
                    duration_ms=int((time.monotonic() - started) * 1000),
                    exit_code=130 if cancelled else 124,
                    dry_run=False,
                    target_summary=target_summary,
                    error_code="EXECUTION_CANCELLED" if cancelled else "EXECUTION_TIMEOUT",
                    timed_out=timed_out,
                )
            exit_code = process.returncode
        except OSError as exc:
            return self._failure(
                f"Unable to launch configured services.sh: {exc}",
                "EXECUTOR_LAUNCH_FAILED",
                target_summary,
                int((time.monotonic() - started) * 1000),
                127 if isinstance(exc, FileNotFoundError) else 126,
            )
        finally:
            with self._process_lock:
                registered = self._processes.get(task_key)
                if registered is not None and process is not None:
                    registered.discard(process)
                    if not registered:
                        self._processes.pop(task_key, None)
                        self._cancelled.discard(task_key)

        parsed = self.parser.parse(stdout, stderr, exit_code)
        status = self._target_status(parsed.state, exit_code, parsed.parse_success)
        return ExecutionResult(
            status=status,
            output=parsed.raw_stdout or None,
            error_message=parsed.raw_stderr or None,
            duration_ms=int((time.monotonic() - started) * 1000),
            exit_code=exit_code,
            dry_run=False,
            service_state=parsed.state.upper(),
            target_summary=target_summary,
            error_code=(
                None
                if status is TargetStatus.SUCCEEDED
                else "OUTPUT_PARSE_FAILED"
                if not parsed.parse_success
                else "SERVICES_COMMAND_FAILED"
            ),
            retryable=parsed.state == "unreachable",
        )

    def _communicate_capped(
        self, process: subprocess.Popen[bytes], timeout: float, task_key: str
    ) -> tuple[bytes, bytes, bool, bool]:
        if not hasattr(process, "stdout"):
            stdout, stderr = process.communicate(timeout=timeout)
            return (
                stdout.encode() if isinstance(stdout, str) else stdout,
                stderr.encode() if isinstance(stderr, str) else stderr,
                False,
                False,
            )
        buffers = [bytearray(), bytearray()]
        truncated = [False, False]

        def drain(stream: object, index: int) -> None:
            while chunk := stream.read(8192):  # type: ignore[attr-defined]
                room = self.config.max_output_bytes - len(buffers[index])
                if room > 0:
                    buffers[index].extend(chunk[:room])
                if len(chunk) > room:
                    truncated[index] = True

        assert process.stdout is not None and process.stderr is not None
        readers = [
            threading.Thread(target=drain, args=(process.stdout, 0), daemon=True),
            threading.Thread(target=drain, args=(process.stderr, 1), daemon=True),
        ]
        for reader in readers:
            reader.start()
        deadline = time.monotonic() + timeout
        timed_out = False
        cancelled = False
        while process.poll() is None:
            if time.monotonic() >= deadline:
                timed_out = True
                break
            with self._process_lock:
                cancelled = task_key in self._cancelled
            if cancelled:
                break
            time.sleep(0.05)
        with self._process_lock:
            cancelled = cancelled or task_key in self._cancelled
        if timed_out or cancelled:
            self._terminate_process_group(process, signal.SIGTERM)
            try:
                process.wait(timeout=self.config.termination_grace_seconds)
            except subprocess.TimeoutExpired:
                self._terminate_process_group(process, signal.SIGKILL)
                process.wait()
        for reader in readers:
            reader.join(timeout=self.config.termination_grace_seconds + 1)
        marker = b"\n[output truncated]\n"
        for index in range(2):
            if truncated[index]:
                keep = max(0, self.config.max_output_bytes - len(marker))
                buffers[index] = buffers[index][:keep] + marker
        return bytes(buffers[0]), bytes(buffers[1]), timed_out, cancelled

    def _validate_request(self, request: ExecutionRequest) -> None:
        checks = {
            "environment": request.environment_code in self.config.allowed_environments,
            "host": request.host_name in self.config.allowed_hosts,
            "service": request.service_name in self.config.allowed_services,
            "action": request.action.value in self.config.allowed_actions,
            "profile capability": request.action in self.capabilities,
        }
        rejected = [name for name, allowed in checks.items() if not allowed]
        if rejected:
            raise ValueError("Execution request is outside allowlists: " + ", ".join(rejected))

    def _validate_paths(self) -> tuple[str, str]:
        if not self.config.script_path:
            raise ValueError("services.script_path is not configured")
        if not self.config.working_directory:
            raise ValueError("services.working_directory is not configured")
        script_input = Path(self.config.script_path)
        working_input = Path(self.config.working_directory)
        if not script_input.is_absolute() or not working_input.is_absolute():
            raise ValueError("services paths must be absolute")
        script = script_input.resolve(strict=True)
        working_directory = working_input.resolve(strict=True)
        if script_input.absolute() != script or working_input.absolute() != working_directory:
            raise ValueError("Symlinks are forbidden in services paths")
        if not script.is_file():
            raise ValueError("Configured services.sh is not a regular file")
        if not os.access(script, os.X_OK):
            raise ValueError("Configured services.sh is not executable")
        if not working_directory.is_dir():
            raise ValueError("Configured services working directory does not exist")
        if self.config.command_profile == "test-fixture-v2" and script != _FIXTURE_SCRIPT:
            raise ValueError("test-fixture-v2 is restricted to the repository fake_services.sh")
        return str(script), str(working_directory)

    def _build_bound_parser(self) -> StatusOutputParser:
        profile_parser = None
        with suppress(CommandProfileNotConfigured, UnknownCommandProfile):
            profile_parser = self._builder.profile.parser
        name = profile_parser or self.config.output_parser
        configured = self.config.output_parsers.get(name)
        if configured is not None:
            return build_status_parser(configured)
        parsers: dict[str, StatusOutputParser] = {
            "json_status": JsonStatusParser(),
            "legacy_text_status": LegacyTextStatusParser(),
            "raw_output": RawOutputParser(),
        }
        if name not in parsers:
            raise ValueError(f"Unsupported output parser: {name}")
        return parsers[name]

    def _validate_process_environment(self) -> None:
        unknown = set(self.config.process_environment) - _ALLOWED_ENVIRONMENT_KEYS
        if unknown:
            raise ValueError("Unsupported services environment keys: " + ", ".join(sorted(unknown)))
        if any(
            "\x00" in key or "\x00" in value
            for key, value in self.config.process_environment.items()
        ):
            raise ValueError("services environment contains NUL bytes")

    @staticmethod
    def _terminate_process_group(
        process: subprocess.Popen[bytes], signal_number: signal.Signals
    ) -> None:
        try:
            os.killpg(process.pid, signal_number)
        except ProcessLookupError:
            return

    @staticmethod
    def _target_status(state: str, exit_code: int, parse_success: bool) -> TargetStatus:
        if state == "timeout":
            return TargetStatus.TIMED_OUT
        if state == "unreachable":
            return TargetStatus.UNREACHABLE
        if exit_code != 0 or state in {"failed", "not_found", "parse_failed"}:
            return TargetStatus.FAILED
        if parse_success and state in {"running", "stopped", "unknown"}:
            return TargetStatus.SUCCEEDED
        return TargetStatus.UNKNOWN

    @staticmethod
    def _failure(
        message: str,
        error_code: str,
        target_summary: str,
        duration_ms: int = 0,
        exit_code: int = 126,
    ) -> ExecutionResult:
        return ExecutionResult(
            status=TargetStatus.FAILED,
            output=None,
            error_message=message,
            duration_ms=duration_ms,
            exit_code=exit_code,
            dry_run=False,
            target_summary=target_summary,
            error_code=error_code,
        )

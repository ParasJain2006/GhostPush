"""Background worker thread for claiming and processing queued GhostPush jobs."""

import threading
from typing import Callable, Optional

from common.errors import GhostPushError
from common.schemas import AgentResponse, SubmissionPayload
from backend.agent.adapter import execute_agent
from backend.config.manager import ConfigManager
from backend.jobs.queue import JobQueue


class JobWorker:
    """Background worker thread that claims QUEUED jobs and executes them via adapter."""

    def __init__(
        self,
        queue: JobQueue,
        poll_interval: float = 0.5,
        api_key_resolver: Optional[Callable[[str], Optional[str]]] = None,
        config_manager: Optional[ConfigManager] = None,
    ):
        self.queue = queue
        self.poll_interval = poll_interval
        self.config_manager = config_manager or ConfigManager()
        self.api_key_resolver = (
            api_key_resolver
            if api_key_resolver is not None
            else self.config_manager.get_api_key
        )
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background worker thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="JobWorkerThread", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the background worker thread to stop."""
        self._stop_event.set()

    def join(self, timeout: Optional[float] = None) -> None:
        """Wait for the worker thread to terminate."""
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def is_alive(self) -> bool:
        """Return True if the worker thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def _run_loop(self) -> None:
        """Worker loop polling for queued jobs until stop signal."""
        while not self._stop_event.is_set():
            processed = self.process_one_job()
            if not processed:
                self._stop_event.wait(timeout=self.poll_interval)

    def process_one_job(self) -> bool:
        """Claim and execute a single QUEUED job.

        Returns True if a job was claimed and processed, False if queue was empty.
        """
        job_rec = self.queue.claim_next_job()
        if not job_rec:
            return False

        job_id = job_rec["job_id"]
        payload_data = job_rec.get("payload", {})

        try:
            payload = SubmissionPayload.model_validate(payload_data)

            # Populate runtime configuration defaults if missing from job payload
            config = self.config_manager.load_config()
            if not payload.ai_provider:
                payload.ai_provider = config.ai_provider
            if not payload.ai_model:
                payload.ai_model = config.ai_model
            if not payload.repository_path:
                payload.repository_path = config.repository_path
            if not payload.remote_repo_url:
                payload.remote_repo_url = config.remote_repo_url

            # Inject runtime API key if resolver provided
            if self.api_key_resolver and payload.ai_provider:
                secret_key = self.api_key_resolver(payload.ai_provider)
                if secret_key:
                    payload.api_key = secret_key

            response = execute_agent(payload)

            if isinstance(response, AgentResponse):
                self.queue.complete_job(job_id, response)
            else:
                msg = str(response)
                self.queue.fail_job(job_id, msg or "Agent execution reported failure.")

        except GhostPushError as e:
            # GhostPushError caught: persist failure details without crashing worker loop
            error_msg = f"GhostPushError [{e.code.value}]: {e.message}"
            self.queue.fail_job(job_id, error_msg)

        except Exception as e:
            # Unexpected exception caught: persist failure details without crashing worker loop
            error_msg = f"Unexpected Exception: {str(e)}"
            self.queue.fail_job(job_id, error_msg)

        return True

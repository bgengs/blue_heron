"""In-memory job runner. One job at a time, daemon thread, SSE-friendly."""

import threading
import time
import traceback
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal, Optional

JobKind = Literal["process", "dryrun", "verify", "publish"]
JobStatus = Literal["queued", "running", "done", "error", "cancelled"]


@dataclass
class Job:
    id: str
    kind: JobKind
    label: str                              # human-readable, e.g. "Process DJI_002"
    status: JobStatus = "queued"
    progress: float = 0.0                   # 0.0..1.0
    current_step: str = ""
    total: int = 0
    completed: int = 0
    log_lines: deque = field(default_factory=lambda: deque(maxlen=300))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    cancel_flag: threading.Event = field(default_factory=threading.Event)
    result: dict = field(default_factory=dict)

    def log(self, line: str) -> None:
        self.log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")

    def set_progress(self, completed: int, total: int, step: str = "") -> None:
        self.completed = completed
        self.total = total
        self.progress = (completed / total) if total > 0 else 0.0
        if step:
            self.current_step = step

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "status": self.status,
            "progress": round(self.progress, 4),
            "current_step": self.current_step,
            "total": self.total,
            "completed": self.completed,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error": self.error,
            "result": self.result,
        }


class JobRunner:
    """Singleton job runner. Holds current + history; runs jobs on a worker thread."""

    def __init__(self):
        self._lock = threading.Lock()
        self._current: Optional[Job] = None
        self._history: deque[Job] = deque(maxlen=50)
        self._all: dict[str, Job] = {}

    @property
    def current(self) -> Optional[Job]:
        return self._current

    def get(self, job_id: str) -> Optional[Job]:
        return self._all.get(job_id)

    def list_recent(self) -> list[Job]:
        items = list(self._history)
        if self._current:
            items.append(self._current)
        return list(reversed(items))

    def submit(self, kind: JobKind, label: str, target: Callable[[Job], None]) -> Job:
        """Submit a new job. Refuses if one is already running."""
        with self._lock:
            if self._current and self._current.status == "running":
                raise RuntimeError(
                    f"A job is already running: {self._current.label}"
                )
            job = Job(id=uuid.uuid4().hex[:12], kind=kind, label=label)
            self._all[job.id] = job
            self._current = job

        def _wrap():
            job.status = "running"
            job.started_at = datetime.now()
            job.log(f"Started: {label}")
            try:
                target(job)
                if job.status == "running":
                    job.status = "done"
                    job.progress = 1.0
                    job.log("Done.")
            except Exception as e:
                job.status = "error"
                job.error = str(e)
                job.log(f"ERROR: {e}")
                job.log_lines.append(traceback.format_exc())
            finally:
                job.finished_at = datetime.now()
                with self._lock:
                    self._history.append(job)
                    if self._current is job:
                        # keep it as "most recent" for SSE viewers
                        pass

        t = threading.Thread(target=_wrap, daemon=True, name=f"job-{job.id}")
        t.start()
        return job

    def cancel(self, job_id: str) -> bool:
        job = self._all.get(job_id)
        if not job or job.status != "running":
            return False
        job.cancel_flag.set()
        job.log("Cancellation requested...")
        return True


# Singleton
runner = JobRunner()

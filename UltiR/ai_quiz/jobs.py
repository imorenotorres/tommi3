"""Background jobs: work that goes on after the request that started it has been answered.

One thread per job, known only to this server process. A job is given a stop
signal, which is set when its time is up or when it is cancelled; the work is
expected to look at it and give up. Work that does not is left to finish on
its own, and whoever started it decides what a late result is worth.

Jobs do not survive a restart. Whatever a job was working on must be recorded
elsewhere (the document index does that), so that work cut short can be told
apart from work still going on: see `is_running`.
"""

import logging
import threading

log = logging.getLogger("ultir.ai_quiz")


class Job:
    def __init__(self, key: str):
        self.key = key
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None
        self.timer: threading.Timer | None = None


_jobs: dict[str, Job] = {}
_guard = threading.Lock()


def key_of(doc_id: str) -> str:
    """The job that reads one document. Document ids are unique across courses."""
    return f"read:{doc_id}"


def start(key: str, work, seconds: float, on_timeout) -> Job:
    """Run `work(stop)` in a thread of its own.

    After `seconds` the stop signal is set and `on_timeout()` is called, once,
    whether or not the work has reacted.
    """
    job = Job(key)

    def run():
        try:
            work(job.stop)
        except Exception:   # noqa: BLE001 - a job must never take the thread down silently
            log.exception("AI Quiz: background job %s failed", key)
        finally:
            job.timer.cancel()
            with _guard:
                if _jobs.get(key) is job:
                    del _jobs[key]

    def expire():
        job.stop.set()
        on_timeout()

    with _guard:
        if key in _jobs:
            raise RuntimeError(f"job {key} is already running")
        _jobs[key] = job
    job.timer = threading.Timer(seconds, expire)
    job.timer.daemon = True
    job.thread = threading.Thread(target=run, name=f"ai-quiz-{key}", daemon=True)
    job.timer.start()
    job.thread.start()
    return job


def is_running(key: str) -> bool:
    with _guard:
        return key in _jobs


def cancel(key: str) -> None:
    """Tell the job to stop. Does not wait for it."""
    with _guard:
        job = _jobs.get(key)
    if job:
        job.stop.set()


def stop_all(seconds: float = 5.0) -> None:
    """Tell every job to stop and wait for them. For shutting down, and for the tests."""
    with _guard:
        jobs = list(_jobs.values())
    for job in jobs:
        job.stop.set()
        job.timer.cancel()
    for job in jobs:
        job.thread.join(seconds)

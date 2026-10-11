"""Stand-ins for a full-reading engine, for tests that need none of the real one."""

import threading

from UltiR.ai_quiz import ingestion

PAGES = [
    "A local feature is an image pattern that differs from its immediate neighbourhood, and it is found again "
    "when the same scene is photographed under different conditions.",
    "The ratio test compares the distance to the nearest neighbour with the distance to the second nearest, "
    "and a match is accepted only when that ratio is below a threshold.",
]


class SlowReader:
    """A full reader that waits until the test lets it finish.

    `started` is set when reading begins. `release()` lets it return its pages.
    With `obeys_stop=False` it ignores the stop signal, like an engine that hangs.
    """

    name = "fake"
    mode = "full"

    def __init__(self, obeys_stop: bool = True, error: Exception | None = None):
        self.obeys_stop = obeys_stop
        self.error = error
        self.started = threading.Event()
        self.finished = threading.Event()
        self._release = threading.Event()
        self.was_stopped = False
        self.calls = 0

    def release(self):
        self._release.set()

    def read(self, path, stop=None):
        self.calls += 1
        self.started.set()
        try:
            while not self._release.wait(0.005):
                if self.obeys_stop and stop is not None and stop.is_set():
                    self.was_stopped = True
                    raise ingestion.ReadingStopped()
            if self.error is not None:
                raise self.error
            return ingestion.ParsedDocument(
                pages=[ingestion.Page(number=i, text=text) for i, text in enumerate(PAGES, start=1)],
                mode="full", engine=self.name)
        finally:
            self.finished.set()


def install(monkeypatch, reader):
    """Make `reader` the full-reading engine of the tool for this test."""
    text_reader = ingestion.get_reader("text")
    monkeypatch.setattr(ingestion, "get_reader", lambda mode: reader if mode == "full" else text_reader)
    monkeypatch.setattr(ingestion, "full_reading_available", lambda: True)
    return reader

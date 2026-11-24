"""Background scan loop. The UI thread only reads a queue of plain events."""

from __future__ import annotations

import queue
import threading

from cursor_auto_run.monitor import Monitor, MonitorConfig
from cursor_auto_run.safety import RunMode
from cursor_auto_run.scanner import default_scanner
from cursor_auto_run.settings_store import Settings


class AppController:
    def __init__(self, scanner_factory=None) -> None:
        self.scanner_factory = scanner_factory or default_scanner
        self.events: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._config = MonitorConfig()
        self._stop = threading.Event()
        self._scan_now = threading.Event()
        self._thread: threading.Thread | None = None
        self.click_count = 0

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def apply(self, settings: Settings) -> None:
        cleaned = settings.cleaned()
        config = MonitorConfig(
            enabled=cleaned.auto_run,
            paused=cleaned.paused,
            mode=RunMode.parse(cleaned.mode),
            delay_ms=cleaned.delay_ms,
            custom_commands=list(cleaned.custom_commands),
            extra_labels=list(cleaned.extra_labels),
        )
        with self._lock:
            self._config = config
            self.click_count = cleaned.click_count

    def start(self) -> None:
        if self.running():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="cursor-auto-run", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=2.0)
        if thread is None or not thread.is_alive():
            self._thread = None

    def request_scan(self) -> None:
        if self.running():
            self._scan_now.set()
            return
        threading.Thread(target=self._oneshot, name="cursor-auto-run-scan", daemon=True).start()

    def drain(self) -> list[tuple]:
        items: list[tuple] = []
        while True:
            try:
                items.append(self.events.get_nowait())
            except queue.Empty:
                break
        return items

    def _loop(self) -> None:
        scanner = self.scanner_factory()
        try:
            prepare = getattr(scanner, "prepare", None)
            if prepare is not None:
                prepare()
            monitor = Monitor(scanner)
            with self._lock:
                monitor.click_count = self.click_count
            while not self._stop.is_set():
                with self._lock:
                    config = self._config
                requested = self._scan_now.is_set()
                self._scan_now.clear()
                try:
                    activities, report = monitor.tick(config, force_log_scan=requested)
                except Exception as exc:
                    self.events.put(("error", str(exc)))
                else:
                    with self._lock:
                        self.click_count = monitor.click_count
                    if activities:
                        self.events.put(("batch", activities, report, monitor.click_count))
                self._stop.wait(0.6)
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            close = getattr(scanner, "close", None)
            if close is not None:
                try:
                    close()
                except Exception:
                    pass

    def _oneshot(self) -> None:
        scanner = self.scanner_factory()
        try:
            prepare = getattr(scanner, "prepare", None)
            if prepare is not None:
                prepare()
            with self._lock:
                config = self._config
            report = scanner.scan(
                extra_labels=list(config.extra_labels),
                custom_rules=list(config.custom_commands),
            )
            self.events.put(("scan", report))
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            close = getattr(scanner, "close", None)
            if close is not None:
                try:
                    close()
                except Exception:
                    pass

"""Background worker thread that processes a queue of videos.

The UI adds videos + encode/upscale options and the worker emits Qt signals
for per-video progress, overall progress, completion, and errors.

We keep this module self-contained so it can be unit-tested without a UI by
constructing a `BatchWorker` and pumping signals into a mock receiver.
"""

from __future__ import annotations

import os
import traceback
from dataclasses import dataclass, field
from typing import Optional

from PyQt5 import QtCore

from .ffmpeg_handler import (
    EncodeOptions,
    FFmpegError,
    VideoInfo,
    process_video,
    probe_video,
)
from .upscale_handler import UpscaleOptions
from ..utils.file_manager import build_output_path


@dataclass
class QueueItem:
    input_path: str
    info: Optional[VideoInfo] = None
    output_path: str = ""
    status: str = "pending"   # "pending" | "running" | "done" | "error" | "cancelled"
    error: str = ""


@dataclass
class BatchJob:
    items: list[QueueItem] = field(default_factory=list)
    output_dir: str = ""
    encode_options: EncodeOptions = None  # type: ignore[assignment]
    upscale_options: UpscaleOptions = field(default_factory=UpscaleOptions)


class BatchWorker(QtCore.QObject):
    """Processes a batch of videos in a background thread."""

    # Signals -------------------------------------------------------------
    item_started = QtCore.pyqtSignal(int)                      # index
    item_progress = QtCore.pyqtSignal(int, float)              # index, 0..1
    item_finished = QtCore.pyqtSignal(int, str)                # index, output_path
    item_failed = QtCore.pyqtSignal(int, str)                  # index, error message
    overall_progress = QtCore.pyqtSignal(float)                # 0..1
    log_message = QtCore.pyqtSignal(str)                       # informational
    batch_finished = QtCore.pyqtSignal(list)                   # list of output paths

    def __init__(self, job: BatchJob, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._job = job
        self._cancel = False

    # ------------------------------------------------------------------
    def cancel(self) -> None:
        self._cancel = True

    def _cancelled(self) -> bool:
        return self._cancel

    # ------------------------------------------------------------------
    @QtCore.pyqtSlot()
    def run(self) -> None:
        total = len(self._job.items)
        if total == 0:
            self.batch_finished.emit([])
            return

        outputs: list[str] = []
        for idx, item in enumerate(self._job.items):
            if self._cancel:
                item.status = "cancelled"
                continue

            item.status = "running"
            self.item_started.emit(idx)

            try:
                info = item.info or probe_video(item.input_path)
                item.info = info

                output_path = item.output_path or build_output_path(
                    item.input_path, self._job.output_dir
                )
                item.output_path = output_path

                options = EncodeOptions(
                    watermark=self._job.encode_options.watermark,
                    target_height=(
                        self._job.upscale_options.target_height
                        if self._job.upscale_options.enabled
                        else None
                    ),
                    video_codec=self._job.encode_options.video_codec,
                    crf=self._job.encode_options.crf,
                    preset=self._job.encode_options.preset,
                    audio_codec=self._job.encode_options.audio_codec,
                    audio_bitrate=self._job.encode_options.audio_bitrate,
                )

                def _pcb(pct: float, _idx: int = idx, _total: int = total) -> None:
                    self.item_progress.emit(_idx, pct)
                    self.overall_progress.emit((_idx + pct) / _total)

                process_video(
                    input_path=item.input_path,
                    output_path=output_path,
                    info=info,
                    options=options,
                    progress_cb=_pcb,
                    cancel_flag=self._cancelled,
                )

                item.status = "done"
                outputs.append(output_path)
                self.item_finished.emit(idx, output_path)
                self.overall_progress.emit((idx + 1) / total)

            except FFmpegError as exc:
                item.status = "error"
                item.error = str(exc)
                self.item_failed.emit(idx, str(exc))
                self.log_message.emit(f"[ERROR] {item.input_path}: {exc}")
            except Exception as exc:  # noqa: BLE001
                item.status = "error"
                item.error = f"{exc}\n{traceback.format_exc()}"
                self.item_failed.emit(idx, str(exc))
                self.log_message.emit(f"[ERROR] {item.input_path}: {exc}")

        self.batch_finished.emit(outputs)

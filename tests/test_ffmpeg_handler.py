"""Tests for ffmpeg_handler: probing, overlay graph construction, full encode."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.processing.ffmpeg_handler import (
    EncodeOptions,
    WatermarkSettings,
    build_command_preview,
    build_overlay_filtergraph,
    probe_video,
    process_video,
)


def test_overlay_text_filtergraph_contains_drawtext() -> None:
    wm = WatermarkSettings(enabled=True, mode="text", text="Hello", position="bottom-right")
    extras, parts = build_overlay_filtergraph(wm, 1920, 1080)
    assert extras == []
    assert len(parts) == 1
    assert "drawtext=" in parts[0]
    assert "[0:v]" in parts[0] and "[vout]" in parts[0]


def test_overlay_text_escapes_special_chars() -> None:
    wm = WatermarkSettings(enabled=True, mode="text", text="a:b'c%d")
    _, parts = build_overlay_filtergraph(wm, 1920, 1080)
    assert r"a\:b\'c\%d" in parts[0]


def test_overlay_disabled_returns_empty() -> None:
    wm = WatermarkSettings(enabled=False)
    extras, parts = build_overlay_filtergraph(wm, 1920, 1080)
    assert extras == []
    assert parts == []


def test_overlay_image_requires_existing_file(tmp_path: Path) -> None:
    wm = WatermarkSettings(enabled=True, mode="image", image_path=str(tmp_path / "nope.png"))
    with pytest.raises(Exception):
        build_overlay_filtergraph(wm, 1920, 1080)


def test_build_command_preview_has_required_flags() -> None:
    wm = WatermarkSettings(enabled=True, mode="text", text="Hi")
    info_like = type("I", (), {"width": 1920, "height": 1080, "duration": 1.0, "fps": 24, "codec": "h264", "path": "x.mp4", "resolution": "1920x1080", "duration_hms": "00:00:01"})
    options = EncodeOptions(watermark=wm, target_height=2160)
    cmd = build_command_preview("in.mp4", "out.mp4", info_like, options)
    assert "ffmpeg" in cmd[0]
    assert "-filter_complex" in cmd
    idx = cmd.index("-filter_complex")
    graph = cmd[idx + 1]
    assert "drawtext=" in graph
    assert "scale=-2:2160" in graph


# -----------------------------------------------------------------------
# Integration tests requiring ffmpeg
# -----------------------------------------------------------------------

def test_probe_video(sample_videos) -> None:
    info = probe_video(str(sample_videos[0]))
    assert info.width == 320
    assert info.height == 240
    assert info.duration > 0
    assert info.codec


def test_process_video_produces_output(sample_videos, tmp_path: Path) -> None:
    src = sample_videos[0]
    out = tmp_path / "processed.mp4"
    info = probe_video(str(src))

    wm = WatermarkSettings(enabled=True, mode="text", text="VBP", position="top-left")
    opts = EncodeOptions(watermark=wm, target_height=480, preset="ultrafast", crf=28)

    progress_values: list[float] = []
    process_video(str(src), str(out), info, opts, progress_cb=progress_values.append)

    assert out.exists()
    assert out.stat().st_size > 0
    # Confirm progress callback was invoked.
    assert len(progress_values) > 0
    assert progress_values[-1] >= 0.9

    # Output should be scaled up to 480p height.
    out_info = probe_video(str(out))
    assert out_info.height == 480


def test_process_video_with_image_overlay(sample_videos, tmp_path: Path) -> None:
    # Create a tiny PNG logo via ffmpeg.
    import subprocess
    logo = tmp_path / "logo.png"
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=red:s=64x32",
            "-frames:v", "1", str(logo),
        ],
        check=True,
    )

    src = sample_videos[0]
    out = tmp_path / "logo_overlay.mp4"
    info = probe_video(str(src))

    wm = WatermarkSettings(
        enabled=True, mode="image", image_path=str(logo),
        position="bottom-right", opacity=0.9, scale=1.0,
    )
    opts = EncodeOptions(watermark=wm, preset="ultrafast", crf=28)
    process_video(str(src), str(out), info, opts)
    assert out.exists()
    assert out.stat().st_size > 0

"""FFmpeg wrapper: probing metadata, building watermark/overlay filter graphs, encoding."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional


class FFmpegError(RuntimeError):
    """Raised when an FFmpeg invocation fails or FFmpeg is unavailable."""


def _which(tool: str) -> Optional[str]:
    """Return the absolute path to `tool` on PATH, or None if missing."""
    return shutil.which(tool)


def ffmpeg_available() -> bool:
    return _which("ffmpeg") is not None


def ffprobe_available() -> bool:
    return _which("ffprobe") is not None


@dataclass
class VideoInfo:
    path: str
    duration: float  # seconds
    width: int
    height: int
    fps: float
    codec: str

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def duration_hms(self) -> str:
        total = int(self.duration)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


def probe_video(path: str) -> VideoInfo:
    """Probe a video file with ffprobe and return structured metadata.

    Raises FFmpegError if ffprobe is missing or the file is invalid.
    """
    if not ffprobe_available():
        raise FFmpegError("ffprobe not found on PATH. Install FFmpeg and retry.")
    if not os.path.isfile(path):
        raise FFmpegError(f"File not found: {path}")

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=30
        )
    except subprocess.CalledProcessError as exc:
        raise FFmpegError(f"ffprobe failed for {path}: {exc.stderr.strip()}") from exc
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"ffprobe timed out for {path}") from exc

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise FFmpegError(f"Could not parse ffprobe output for {path}") from exc

    video_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    if not video_streams:
        raise FFmpegError(f"No video stream found in {path}")

    v = video_streams[0]
    width = int(v.get("width", 0))
    height = int(v.get("height", 0))
    codec = v.get("codec_name", "unknown")

    fps = 0.0
    r_rate = v.get("r_frame_rate") or v.get("avg_frame_rate") or "0/1"
    if "/" in r_rate:
        num, den = r_rate.split("/", 1)
        try:
            n, d = float(num), float(den)
            fps = n / d if d else 0.0
        except ValueError:
            fps = 0.0

    duration = 0.0
    if "duration" in v:
        try:
            duration = float(v["duration"])
        except (TypeError, ValueError):
            duration = 0.0
    if not duration and "format" in data:
        try:
            duration = float(data["format"].get("duration", 0.0))
        except (TypeError, ValueError):
            duration = 0.0

    return VideoInfo(
        path=path,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        codec=codec,
    )


# ---------------------------------------------------------------------------
# Filter graph construction
# ---------------------------------------------------------------------------

POSITION_EXPRS = {
    # (x_expr, y_expr) relative to (main W/H, overlay w/h) with 12px padding.
    "top-left":     ("12",            "12"),
    "top-right":    ("W-w-12",        "12"),
    "center":       ("(W-w)/2",       "(H-h)/2"),
    "bottom-left":  ("12",            "H-h-12"),
    "bottom-right": ("W-w-12",        "H-h-12"),
    "bottom":       ("(W-w)/2",       "H-h-12"),
    "top":          ("(W-w)/2",       "12"),
}


@dataclass
class WatermarkSettings:
    """User-controlled overlay settings. Either text or image_path must be set."""
    enabled: bool = False
    mode: str = "text"  # "text" or "image"
    text: str = ""
    image_path: str = ""
    position: str = "bottom-right"  # or "custom"
    custom_x: int = 0
    custom_y: int = 0
    opacity: float = 0.8            # 0.0 - 1.0
    scale: float = 1.0              # relative scale multiplier
    font_size: int = 36
    font_color: str = "white"
    font_file: str = ""             # path to a .ttf / .otf file (optional)
    shadow: bool = True             # drop shadow behind text
    bounce: bool = False            # DVD-screensaver style animation
    bounce_speed: str = "slow"      # "slow" | "medium" | "fast"


def _escape_drawtext(text: str) -> str:
    """Escape a string for use inside an ffmpeg drawtext `text=` parameter."""
    # Order matters: escape backslashes first.
    text = text.replace("\\", "\\\\")
    text = text.replace(":", r"\:")
    text = text.replace("'", r"\'")
    text = text.replace("%", r"\%")
    return text


def _pos_exprs(settings: WatermarkSettings) -> tuple[str, str]:
    if settings.position == "custom":
        return (str(int(settings.custom_x)), str(int(settings.custom_y)))
    return POSITION_EXPRS.get(settings.position, POSITION_EXPRS["bottom-right"])


# DVD-screensaver pixels-per-second for each speed preset. We use slightly
# different X/Y velocities so the overlay doesn't move along a perfect 45°
# line — looks more natural.
BOUNCE_SPEEDS: dict[str, tuple[int, int]] = {
    "slow":   (40, 28),
    "medium": (90, 63),
    "fast":   (160, 112),
}


def _bounce_exprs_text(speed: str) -> tuple[str, str]:
    """Return ffmpeg drawtext x/y expressions for a DVD-style bounce.

    Uses a triangle wave: `abs(mod(t*v, 2*(w-text_w)) - (w-text_w))` oscillates
    between 0 and (w-text_w). `text_w` / `text_h` are drawtext-specific
    variables that resolve to the rendered glyph box.
    """
    vx, vy = BOUNCE_SPEEDS.get(speed, BOUNCE_SPEEDS["slow"])
    x = f"abs(mod(t*{vx}\\,2*(w-text_w))-(w-text_w))"
    y = f"abs(mod(t*{vy}\\,2*(h-text_h))-(h-text_h))"
    return x, y


def _bounce_exprs_overlay(speed: str) -> tuple[str, str]:
    """Return ffmpeg overlay x/y expressions for a DVD-style image bounce.

    For the overlay filter, main video dimensions are `W`/`H` and the overlay
    is `w`/`h`. Note: unlike drawtext, overlay expressions use `:` as the arg
    separator so commas inside `mod()` do NOT need escaping.
    """
    vx, vy = BOUNCE_SPEEDS.get(speed, BOUNCE_SPEEDS["slow"])
    # Escape commas so the filter-graph parser does not split on them.
    x = f"abs(mod(t*{vx}\\,2*(W-w))-(W-w))"
    y = f"abs(mod(t*{vy}\\,2*(H-h))-(H-h))"
    return x, y


def _escape_fontfile(path: str) -> str:
    """Escape a font file path for FFmpeg's drawtext `fontfile=` parameter."""
    path = path.replace("\\", "/")
    path = path.replace(":", r"\:")
    path = path.replace("'", r"\'")
    return path


def build_overlay_filtergraph(
    settings: WatermarkSettings,
    base_width: int,
    base_height: int,
) -> tuple[list[str], list[str]]:
    """Return (extra_input_args, filter_complex_parts) for an overlay.

    The caller is responsible for prepending the primary `-i input.mp4` and
    joining `filter_complex_parts` with `;`. Image inputs are loaded with
    `-loop 1` so a still image stays stable across the whole duration of the
    main video (this is what fixes the "bouncing" issue).
    """
    if not settings.enabled:
        return [], []

    x_expr, y_expr = _pos_exprs(settings)

    if settings.mode == "image":
        if not settings.image_path or not os.path.isfile(settings.image_path):
            raise FFmpegError(f"Watermark image not found: {settings.image_path!r}")
        if settings.bounce:
            x_expr, y_expr = _bounce_exprs_overlay(settings.bounce_speed)
        # Scale overlay relative to main width (10% default * scale multiplier).
        target_w = max(1, int(base_width * 0.1 * settings.scale))
        # -loop 1 keeps the still image alive for the whole video duration;
        # without it, FFmpeg would emit a single frame and the overlay would
        # flash/disappear (the "bouncing" the user reported).
        extra_inputs = ["-loop", "1", "-i", settings.image_path]
        fc = [
            # Normalize SAR so overlay doesn't stretch or jitter on mixed aspect
            # sources, and force rgba so alpha blending is consistent.
            f"[1:v]scale={target_w}:-1:flags=lanczos,setsar=1,format=rgba,"
            f"colorchannelmixer=aa={settings.opacity:.3f}[wm]",
            f"[0:v][wm]overlay={x_expr}:{y_expr}:shortest=1[vout]",
        ]
        return extra_inputs, fc

    # text mode
    text = _escape_drawtext(settings.text or "")
    if not text:
        return [], []
    font_size = max(8, int(settings.font_size * settings.scale))
    alpha = max(0.0, min(1.0, settings.opacity))
    font_clause = ""
    if settings.font_file and os.path.isfile(settings.font_file):
        font_clause = f"fontfile='{_escape_fontfile(settings.font_file)}':"

    if settings.bounce:
        x_expr, y_expr = _bounce_exprs_text(settings.bounce_speed)

    # Build drawtext parameters. We pair a semi-transparent box with a
    # drop-shadow for a professional CapCut-style overlay.
    parts = [
        f"drawtext={font_clause}text='{text}'",
        f"fontcolor={settings.font_color}@{alpha:.3f}",
        f"fontsize={font_size}",
        f"x={x_expr}",
        f"y={y_expr}",
        f"box=1",
        f"boxcolor=black@{max(0.0, alpha - 0.3):.3f}",
        f"boxborderw=8",
    ]
    if settings.shadow:
        parts.extend([
            f"shadowcolor=black@{max(0.3, alpha * 0.8):.3f}",
            "shadowx=2",
            "shadowy=2",
        ])
    drawtext = ":".join(parts)
    return [], [f"[0:v]{drawtext}[vout]"]


# ---------------------------------------------------------------------------
# Encode with optional overlay + optional scale + optional sharpen
# ---------------------------------------------------------------------------

@dataclass
class EncodeOptions:
    watermark: WatermarkSettings
    target_height: Optional[int] = None   # e.g. 2160 for 4K; None = keep
    video_codec: str = "libx264"
    crf: int = 20
    preset: str = "medium"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    sharpen: bool = False                 # apply `unsharp` filter for a crisp
                                          # CapCut-style ultra-HD look
    sharpen_amount: float = 0.8           # 0 (none) - 1.5 (very sharp)
    pixel_format: str = "yuv420p"         # broadly compatible output pix fmt


ProgressCallback = Callable[[float], None]
# progress: 0.0 - 1.0


_TIME_RE = re.compile(r"out_time_ms=(\d+)")


def _chain_post_filters(
    filter_parts: list[str],
    options: EncodeOptions,
    info: VideoInfo,
) -> list[str]:
    """Append optional scale + sharpen filters after the overlay step.

    We re-label the terminal `[vout]` sink so subsequent filters can chain on.
    """
    post: list[str] = []
    do_scale = (
        options.target_height
        and options.target_height > 0
        and options.target_height != info.height
    )
    do_sharpen = options.sharpen and options.sharpen_amount > 0

    if not do_scale and not do_sharpen:
        return filter_parts

    last = filter_parts[-1]
    last_no_sink = last.rsplit("[vout]", 1)[0]
    chain = [f"{last_no_sink}[pre_post]"]

    stages: list[str] = []
    if do_scale:
        stages.append(f"scale=-2:{int(options.target_height)}:flags=lanczos")
    if do_sharpen:
        # unsharp: luma_msize_x:luma_msize_y:luma_amount:chroma_msize_x:chroma_msize_y:chroma_amount
        a = max(0.0, min(1.5, float(options.sharpen_amount)))
        stages.append(f"unsharp=5:5:{a:.2f}:5:5:0.0")

    chain.append(f"[pre_post]{','.join(stages)}[vout]")
    return filter_parts[:-1] + [";".join(chain)]


def process_video(
    input_path: str,
    output_path: str,
    info: VideoInfo,
    options: EncodeOptions,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_flag: Optional[Callable[[], bool]] = None,
) -> None:
    """Run a full encode with overlay + optional upscale + optional sharpen.

    `progress_cb` is invoked with a 0.0-1.0 float as FFmpeg emits progress.
    `cancel_flag` is a callable that returns True when processing should abort.
    """
    if not ffmpeg_available():
        raise FFmpegError("ffmpeg not found on PATH. Install FFmpeg and retry.")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

    extra_inputs, filter_parts = build_overlay_filtergraph(
        options.watermark, info.width, info.height
    )

    # If no overlay, we still need a label for scaling.
    if not filter_parts:
        filter_parts = ["[0:v]null[vout]"]

    filter_parts = _chain_post_filters(filter_parts, options, info)
    filter_complex = ";".join(filter_parts)

    cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-progress", "pipe:1",
        "-nostats",
        "-i", input_path,
    ]
    cmd.extend(extra_inputs)
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "0:a?",
        "-c:v", options.video_codec,
        "-preset", options.preset,
        "-crf", str(options.crf),
        "-pix_fmt", options.pixel_format,
        "-c:a", options.audio_codec,
        "-b:a", options.audio_bitrate,
        "-movflags", "+faststart",
        output_path,
    ])

    total_duration_s = max(info.duration, 0.001)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if cancel_flag and cancel_flag():
                proc.terminate()
                raise FFmpegError("Processing cancelled by user.")
            line = line.strip()
            m = _TIME_RE.search(line)
            if m and progress_cb:
                out_ms = int(m.group(1))
                elapsed_s = out_ms / 1_000_000.0
                pct = min(1.0, elapsed_s / total_duration_s)
                progress_cb(pct)
            if line == "progress=end" and progress_cb:
                progress_cb(1.0)
    finally:
        proc.stdout.close() if proc.stdout else None
        rc = proc.wait()
        stderr = proc.stderr.read() if proc.stderr else ""
        if proc.stderr:
            proc.stderr.close()
        if rc != 0:
            raise FFmpegError(
                f"FFmpeg exited with code {rc} for {input_path}:\n{stderr.strip()}"
            )


def ffmpeg_version() -> str:
    """Return the first line of `ffmpeg -version`, or '' if unavailable."""
    if not ffmpeg_available():
        return ""
    try:
        out = subprocess.check_output(["ffmpeg", "-version"], text=True, timeout=5)
        return out.splitlines()[0] if out else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def build_command_preview(
    input_path: str,
    output_path: str,
    info: VideoInfo,
    options: EncodeOptions,
) -> list[str]:
    """Return the ffmpeg command that would be executed (for tests / UI preview)."""
    extra_inputs, filter_parts = build_overlay_filtergraph(
        options.watermark, info.width, info.height
    )
    if not filter_parts:
        filter_parts = ["[0:v]null[vout]"]
    filter_parts = _chain_post_filters(filter_parts, options, info)
    filter_complex = ";".join(filter_parts)

    cmd: list[str] = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", input_path,
    ]
    cmd.extend(extra_inputs)
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "0:a?",
        "-c:v", options.video_codec,
        "-preset", options.preset,
        "-crf", str(options.crf),
        "-pix_fmt", options.pixel_format,
        "-c:a", options.audio_codec,
        "-b:a", options.audio_bitrate,
        "-movflags", "+faststart",
        output_path,
    ])
    return cmd


# ---------------------------------------------------------------------------
# Built-in quality presets (Digitalinos templates)
# ---------------------------------------------------------------------------

@dataclass
class QualityTemplate:
    """Preset-style knobs for the encoder. Applied on top of user watermark."""
    name: str
    target_height: Optional[int]   # None = keep source height
    preset: str                    # x264 preset
    crf: int                       # lower = better quality
    sharpen: bool
    sharpen_amount: float
    audio_bitrate: str = "192k"


QUALITY_TEMPLATES: dict[str, QualityTemplate] = {
    "Original (no changes)": QualityTemplate(
        name="Original (no changes)",
        target_height=None, preset="medium", crf=20,
        sharpen=False, sharpen_amount=0.0,
    ),
    "YouTube 1080p Clean": QualityTemplate(
        name="YouTube 1080p Clean",
        target_height=1080, preset="slow", crf=19,
        sharpen=True, sharpen_amount=0.6,
    ),
    "CapCut Ultra HD (1440p)": QualityTemplate(
        name="CapCut Ultra HD (1440p)",
        target_height=1440, preset="slow", crf=18,
        sharpen=True, sharpen_amount=0.9,
    ),
    "4K Crisp (2160p)": QualityTemplate(
        name="4K Crisp (2160p)",
        target_height=2160, preset="slow", crf=17,
        sharpen=True, sharpen_amount=1.0,
    ),
    "Fast Preview": QualityTemplate(
        name="Fast Preview",
        target_height=720, preset="ultrafast", crf=26,
        sharpen=False, sharpen_amount=0.0,
        audio_bitrate="128k",
    ),
}


def apply_quality_template(options: EncodeOptions, template_name: str) -> EncodeOptions:
    """Return a new EncodeOptions with the named template applied on top.

    Unknown template names return `options` unchanged.
    """
    tpl = QUALITY_TEMPLATES.get(template_name)
    if not tpl:
        return options
    return EncodeOptions(
        watermark=options.watermark,
        target_height=tpl.target_height if tpl.target_height is not None else options.target_height,
        video_codec=options.video_codec,
        crf=tpl.crf,
        preset=tpl.preset,
        audio_codec=options.audio_codec,
        audio_bitrate=tpl.audio_bitrate,
        sharpen=tpl.sharpen,
        sharpen_amount=tpl.sharpen_amount,
        pixel_format=options.pixel_format,
    )

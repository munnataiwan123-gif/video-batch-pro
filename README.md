# Video Batch Pro

A fully-offline, open-source desktop batch video processor — like a simplified Wondershare UniConverter — written in Python + PyQt5. It supports:

- **Batch video upload** (drag-and-drop or file chooser) with per-file duration/resolution/size.
- **Watermarking**: image logo *or* text overlay, with position / opacity / scale / font-size controls.
- **AI upscaling** via **Real-ESRGAN** (ncnn-vulkan, runs locally — no API calls). Falls back to FFmpeg Lanczos scaling if Real-ESRGAN is not installed.
- **Batch processing engine** using FFmpeg with per-file + overall progress bars and cancellation.
- **Export**: processed videos are written to a chosen folder and can be bundled into a single **ZIP** archive with one click.
- **Presets**: save/load your favourite settings (e.g. "YouTube watermark", "4K upscale + logo") as JSON.
- **Clean dark-mode UI** that stays responsive during processing (all work runs on a background thread).
- **Offline-only**: no network calls, no telemetry.

Primary target: **Windows**. Also runs on macOS and Linux.

---

## Screens

```
┌─────────────────────────────────────────────────────────────────────┐
│ Video Batch Pro          FFmpeg ✓   ·   Real-ESRGAN ✗ (fallback)    │
├──────────────────────────────────┬──────────────────────────────────┤
│ Videos                           │ Settings                         │
│   [Add] [Remove] [Clear]         │  ┌ Watermark │ Upscale │ ... ┐  │
│   ┌────────────────────────┐     │  │ [ ] Enable                │  │
│   │ sample.mp4  1920x1080  │     │  │ Type: text ▾              │  │
│   │ clip.mov    1280x720   │     │  │ Text: @YourChannel        │  │
│   └────────────────────────┘     │  │ Position: bottom-right ▾  │  │
│   Drag & drop video files here   │  │ Opacity ━━━━━○──── 80%    │  │
│                                  │  │ Scale   ━━○──────── 100%  │  │
├──────────────────────────────────┴──────────────────────────────────┤
│ Overall: ████████████░░░░░░░░░░  60%                                │
│ [Process All] [Cancel]                 [Open Output] [Export ZIP]   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Project Layout

```
video_batch_pro/
├── app/
│   ├── main.py                   # entry point
│   ├── ui/
│   │   ├── main_window.py        # main window (PyQt5)
│   │   ├── widgets.py            # drop list, cards, labeled sliders
│   │   └── styles.py             # dark-mode QSS
│   ├── processing/
│   │   ├── ffmpeg_handler.py     # probing, overlay graph, encoding
│   │   ├── upscale_handler.py    # Real-ESRGAN + FFmpeg fallback
│   │   └── queue_manager.py      # threaded batch worker
│   └── utils/
│       ├── file_manager.py       # path helpers, validation
│       ├── zip_export.py         # ZIP packager
│       └── presets.py            # JSON preset save/load
├── tests/                        # pytest suite (auto-skips if FFmpeg missing)
├── run.py                        # `python run.py` launcher
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

---

## Setup

### 1. Python dependencies

You need **Python 3.9+**.

```bash
# Clone
git clone https://github.com/<your-account>/video-batch-pro.git
cd video-batch-pro

# (Recommended) virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install runtime deps
pip install -r requirements.txt
```

### 2. FFmpeg (required)

Video Batch Pro shells out to `ffmpeg` and `ffprobe` — they must be on `PATH`.

**Windows**

1. Download a static build from <https://www.gyan.dev/ffmpeg/builds/> (pick the **release full** build) or <https://github.com/BtbN/FFmpeg-Builds/releases>.
2. Extract the ZIP to `C:\ffmpeg`.
3. Add `C:\ffmpeg\bin` to your **System PATH**:
   - *Start ▶ "Edit the system environment variables" ▶ Environment Variables ▶ Path ▶ Edit ▶ New ▶ `C:\ffmpeg\bin`*.
4. Open a new terminal and verify:
   ```powershell
   ffmpeg -version
   ffprobe -version
   ```

**macOS**

```bash
brew install ffmpeg
```

**Linux (Debian/Ubuntu)**

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

When you launch the app, the header shows "FFmpeg ✓" if it was detected.

### 3. Real-ESRGAN (optional, for AI upscaling)

Video Batch Pro integrates the portable **`realesrgan-ncnn-vulkan`** binary (no Python dependencies, no API calls, runs on your GPU via Vulkan). If it's not installed, upscaling transparently falls back to FFmpeg's Lanczos scaler.

1. Download the pre-built binary from <https://github.com/xinntao/Real-ESRGAN/releases> (or the maintained fork <https://github.com/upscayl/upscayl-ncnn>). Pick the build matching your OS:
   - Windows: `realesrgan-ncnn-vulkan-<ver>-windows.zip`
   - macOS:   `realesrgan-ncnn-vulkan-<ver>-macos.zip`
   - Linux:   `realesrgan-ncnn-vulkan-<ver>-ubuntu.zip`
2. Extract it. The archive contains `realesrgan-ncnn-vulkan` (or `.exe`), plus a `models/` directory with the bundled weights (e.g. `realesr-animevideov3`, `realesrgan-x4plus`).
3. Put the folder somewhere permanent (e.g. `C:\tools\realesrgan`) and add it to your `PATH` the same way as FFmpeg, or drop the binary next to your FFmpeg binary.
4. Verify:
   ```bash
   realesrgan-ncnn-vulkan -h
   ```
5. Relaunch Video Batch Pro — the header should now show "Real-ESRGAN ✓".

> **Vulkan driver note (Windows)**: Real-ESRGAN requires a working Vulkan driver. Most modern GPU drivers ship with one; run `vulkaninfoSDK` or `vulkaninfo` if you want to confirm.

---

## Running the app

```bash
python run.py
```

or, after `pip install -e .`:

```bash
video-batch-pro
```

### Typical workflow

1. Drag video files into the left panel (or use *Add Videos…*).
2. Open the **Watermark** tab and choose *text* or *image*, tweak position/opacity/scale.
3. (Optional) In the **Upscale** tab, enable upscaling and pick a target resolution + backend.
4. (Optional) **Output** tab: choose the output folder and x264 preset/CRF.
5. Click **Process All**. Progress is shown per file and overall.
6. Click **Export All as ZIP** to package the outputs into a single archive.
7. Save your configuration as a preset in the **Presets** tab (e.g. "YouTube watermark").

---

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

The test suite:

- Validates pure-Python helpers (filters, presets, ZIP export, path building).
- If `ffmpeg` / `ffprobe` are available on `PATH`, also runs **integration tests** that:
  - Generate synthetic clips via `ffmpeg -f lavfi`,
  - Probe them with `ffprobe`,
  - Apply text + image overlays,
  - Upscale with FFmpeg,
  - Export outputs as a ZIP archive and check the contents.

Tests that require FFmpeg are **skipped automatically** when it is not installed.

---

## Error handling

- Files that are not valid videos are rejected with a clear dialog ("Cannot read video: …").
- FFmpeg stderr is captured and shown in the status bar on failure.
- If FFmpeg is missing, a warning dialog appears at startup and **Process All** is blocked with an explanation.
- Each file's state is tracked independently: a single bad file does not abort the batch.
- Cancellation mid-batch is supported (terminates the current FFmpeg process cleanly).

---

## License

MIT — see the standard MIT text. Third-party components (FFmpeg, Real-ESRGAN) carry their own licenses.

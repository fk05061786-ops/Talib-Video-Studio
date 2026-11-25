# Build and Deployment Instructions

## 1. Prerequisites (Windows)

- Python 3.10+ (`python --version`)
- PySide6 and PyInstaller (installed below)
- FFmpeg + ffprobe, either:
  - on `PATH`, or
  - copied into `bin/` in the project root before building (recommended for a
    self-contained deployment).

Verify FFmpeg: `ffmpeg -version` and `ffprobe -version`.

## 2. Setup and checks (from the repository root)

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests
python src\main.py
```

The last command must open the GUI without a console error. Top-level failures
are written to `talib_video_studio_error.log` in the current directory.

## 3. Build the executable

```bat
python scripts\build_exe.py
```

The script validates required files, installs PyInstaller if missing, runs the
spec with `--clean`, and expects:

```
dist\TalibVideoStudio\TalibVideoStudio.exe
```

To bundle FFmpeg, place `ffmpeg.exe` and `ffprobe.exe` in `bin\` **before**
running the script; the spec copies them to `bin\` inside the distribution.

## 4. Binary resolution order

At runtime the app resolves FFmpeg/ffprobe in this order:

1. `FFMPEG_PATH` / `FFPROBE_PATH` in `.env.hub` or the process environment
2. `bin\ffmpeg.exe` / `bin\ffprobe.exe` inside the bundle
3. The system `PATH`

Set them in `.env.hub` as `FFMPEG_PATH="C:\ffmpeg\bin\ffmpeg.exe"` if needed.

## 5. Live GUI + `.mp4` export test

1. Copy `dist\TalibVideoStudio` to the target machine.
2. Run `TalibVideoStudio.exe`.
3. Click **Import Video**, choose a short `.mp4` (e.g. 3–10 s).
4. Confirm: the player shows the clip, the Source monitor shows it, the timeline
   shows a V1 and A1 clip, and the audio clip draws a waveform.
5. Press **Play / Pause / Stop**, step with `< Frame` / `Frame >`, scrub the
   scrubber and confirm the timeline playhead follows.
6. Drag a clip body to a new position/track, drag an edge to trim, use **Razor**
   to split, toggle **Snap** / **Ripple**, select two overlapping clips and click
   **Xfade**.
7. Open the **Export Effects** dock tab, enter text, pick `lower_third`, and set
   a From/To window.
8. Click **Export Video** on the toolbar, choose an output path such as
   `C:\temp\test_export.mp4`, and confirm completion.
9. Play `test_export.mp4` in a media player and verify frames, audio, and the
   text overlay. If FFmpeg is missing, the dialog reports the exact binary path
   it tried; check `talib_video_studio_error.log`.

## 6. Troubleshooting

- Missing DLLs / plugins: install the Visual C++ redistributable and rebuild.
- Black video preview: confirm the media codec is supported by Qt Multimedia.
- `FFmpeg binary not found`: set `FFMPEG_PATH` or copy the binary into `bin\`.
- Rebuild cleanly: delete `build\` and `dist\`, then rerun `build_exe.py`.

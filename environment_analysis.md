# Talib Video Studio Environment & Capabilities Analysis

## 1. Available Capabilities & Context

### Core Architecture
- **Python + PySide6 GUI desktop NLE** with Qt-based UI
- **Timeline-based editing** with multi-track support (video + audio tracks)
- **FFmpeg integration** for all video processing (export, thumbnail generation, waveform extraction)
- **Undo/redo system** using full state snapshots (TimelineState + UndoStack)
- **Project serialization** as JSON (.tvs format) with media clips, sequences, settings
- **Pure Python/Qt-free core logic** (timeline_ops, transitions, undo, timecode, media) for headless testing

### Key Components

| Module | Purpose |
|--------|---------|
| `src/core/timeline.py` | TimelineItem, TimelineTrack, TimelineManager data model |
| `src/core/timeline_ops.py` | Pure geometry: snap, trim, ripple, razor, overlap resolution |
| `src/core/undo.py` | Undo/redo stack with full snapshot persistence |
| `src/core/export.py` | FFmpegExporter + ExportWorkerThread for background encoding |
| `src/core/transitions.py` | Transition creation (crossfade/dissolve) with offset calculation |
| `src/core/media.py` | Media info (ffprobe), duration, frame extraction, thumbnails |
| `src/core/audio.py` | Waveform peak extraction (PCM parsing + FFmpeg) |
| `src/core/timecode.py` | Timecode formatting (HH:MM:SS:FF) and frame math |
| `src/app/project.py` | Project class + MediaClip dataclass + save/load |
| `src/app/session.py` | Session state (window, panels, recent projects) |
| `src/utils/packaging.py` | Binary resolution, PyInstaller command generation |
| `src/ui/main_window.py` | Main window with action bar, player, timeline, monitor, export dock |
| `src/ui/panels/timeline.py` | TimelineView + VisualClipItem + drag/trim/razor/snap logic |
| `src/ui/panels/export_panel.py` | Export configuration UI (resolution, FPS, speed, volume, text) |
| `src/ui/panels/monitor.py` | Source/Program monitor with timecode, In/Out points |
| `src/ui/player.py` | VideoPlayerWidget with QMediaPlayer playback, trim controls |
| `src/ui/dialogs.py` | ImportMediaDialog + ExportSettingsDialog |

### Runtime Dependencies
- PySide6 (Qt6 for GUI)
- FFmpeg/ffprobe CLI binaries (must be available at runtime)
- Standard library: json, subprocess, pathlib, dataclasses, typing

### Build System
- PyInstaller spec (`talib_video_studio.spec`) for Windows EXE bundling
- `.env.hub` for environment variable configuration (FFmpeg paths, etc.)
- `scripts/build_exe.py` for build orchestration
- Requirements in `requirements.txt`

### Tests
- 19 test files in `tests/test_core/` covering timeline geometry, overlap rules, ripple/razor operations
- All core tests are Qt-free and can run headless
- Export and UI tests require actual media files and Qt display

## 2. Useful Repos, Libraries & Patterns for Fast NLE Development

### Core Libraries (already in codebase, proven patterns)

**Timeline & Edit Geometry** (already implemented, battle-tested):
- `src/core/timeline_ops.py` — clamp, snap_position, track_from_y, overlapping_clip, resolve_move, resolve_trim, ripple_shift, razor_segments
- `src/core/undo.py` — UndoStack with TimelineState snapshots, deterministic undo/redo
- `src/core/timeline.py` — TimelineManager with overlap prevention, track management

**Transitions** (already implemented):
- `src/core/transitions.py` — make_transition(), xfade_offsets() for FFmpeg xfade/acrossfade offsets

**Media Inspection & FFmpeg**:
- `src/core/media.py` — get_media_info(), get_media_duration(), extract_frame(), get_clip_thumbnail()
- `src/utils/ffmpeg.py` — FFmpegExporter with build_command(), export_video(), build_concat_command()
- `src/core/audio.py` — pcm_to_peaks(), extract_waveform_peaks(), resample_peaks(), peaks_to_bars()

**Project Persistence**:
- `src/app/project.py` — Project + MediaClip + Sequence + save_project/load_project JSON
- `src/app/session.py` — Session state management

**UI Patterns** (PySide6):
- `src/ui/main_window.py` — MainWindow with dock widgets, action bar, central splitter
- `src/ui/panels/timeline.py` — TimelineView with drag/trim/razor/snap, VisualClipItem
- `src/ui/panels/export_panel.py` — Export configuration with effect controls
- `src/ui/panels/monitor.py` — Source/Program monitor with timecode overlays
- `src/ui/player.py` — VideoPlayerWidget with QMediaPlayer playback + trim

### External Libraries to Consider (not yet in codebase)

**Timeline/Geometry (could replace/customize existing)**:
- `python-duration` — human-readable duration parsing
- `timedelta` utilities already in `timecode.py` cover most needs

**Waveform/DSP**:
- `audioread` + `librosa` — advanced audio analysis (currently using raw FFmpeg + PCM parsing)
- `numpy` — for peak bucket operations (currently pure Python loops)

**Testing**:
- `pytest` — standard test runner (codebase uses unittest)
- `pytest-qt` — Qt test fixtures (would need for UI tests)
- `testcontainers` — not relevant for desktop NLE

**Packaging/Build**:
- `PyInstaller` — already used (spec file exists)
- `auto-py-to-exe` — GUI for PyInstaller config
- `py2exe`, `cx_Freeze` — alternatives, but PyInstaller is already configured

**UI/Theme**:
- `qtawesome` — SVG-based Qt icons (codebase uses inline styles/colors)
- `pyqtsvg` — QSvgWidget for scalable icons
- `stylesheets` — codebase uses custom QSS (theme.qss)

**File Dialogs** (already using Qt):
- `QFileDialog` — already used throughout
- `filedialog` enhancements: `fd sherlock` for path validation

### Headless vs. Windows/macOS Applicability

| Feature | Headless (this env) | Windows/macOS |
|---------|---------------------|---------------|
| Core timeline ops | ✅ Fully testable (no Qt) | ✅ Same code |
| Undo/redo system | ✅ Fully testable | ✅ Same code |
| Media info (ffprobe) | ✅ Works if ffprobe available | ✅ Same |
| FFmpeg export | ✅ Works if ffmpeg available | ✅ Same |
| Waveform extraction | ✅ Works if ffmpeg available | ✅ Same |
| Transition math | ✅ Fully testable | ✅ Same |
| Project serialization | ✅ Fully testable | ✅ Same |
| GUI/UI components | ❌ Requires Qt display | ✅ Full PySide6 |
| QMediaPlayer playback | ❌ Requires display/audio | ✅ Full Qt Multimedia |
| File dialogs | ❌ Requires Qt | ✅ Full Qt |
| PyInstaller build | ✅ Can generate spec | ✅ Full build with binaries |

## 3. Practical Speed & Quality Recommendations

### Immediate Wins (no new deps)

1. **Leverage existing pure-Python geometry** — All timeline operations (snap, trim, ripple, razor) are already implemented in `src/core/timeline_ops.py` and tested. New features should reuse these functions rather than reimplementing.

2. **Use existing FFmpegExporter pattern** — `src/utils/ffmpeg.py` already has `build_command()` and `export_video()`. New export features (filters, transitions) should follow the same pattern: build filter string → run subprocess → check return code.

3. **Reuse existing undo/redo** — `src/core/undo.py` + `src/ui/panels/timeline.py` already provide full snapshot-based undo/redo. Any clip operation (move, trim, split, delete) should go through theUndoStack.

4. **Keep core Qt-free** — The codebase already separates core logic (timeline_ops, transitions, undo, timecode, media) from UI (PySide6 widgets). New algorithms should stay in the core modules to maintain testability.

5. **Export with trim ranges** — The export flow already supports trim ranges via `start_sec`/`duration_sec` parameters. The `MainWindow.handle_export()` correctly converts trim_range_ms (ms) to start_sec/duration_sec (s). Keep this pattern.

### Medium-term Improvements

6. **Add FFT-based waveform** — Current `src/core/audio.py` uses simple peak extraction. Consider adding `librosa` or `numpy`-based RMS/centroid features for better visual waveforms, but keep the existing FFmpeg-based fallback.

7. **Add more transition kinds** — Currently only "crossfade" and "dissolve" in `src/core/transitions.py`. Consider adding "wipe", "slide", "zoom" if needed, following the same `make_transition()` pattern.

8. **Text overlay improvements** — `src/core/text_styles.py` (referenced but not fully read) already has `build_drawtext()`, `style_from_dict()`, `TEXT_PRESETS`, `POSITIONS`. The export panel uses these. Consider adding more preset positions or kernel-based text rendering.

9. **Error handling consistency** — The codebase has varied error handling patterns. Consider standardizing on: validate → run → check return code → emit signal → show QMessageBox, as seen in `MainWindow.handle_export()` and `ExportPanel._start_export()`.

10. **Add timeline zoom/pan persistence** — Currently `_zoom` and `_ms_to_px` are set up in `TimelinePanel` but not persisted across sessions. Could add to `Session` or `Project` serialization.

### Things to Avoid

- ❌ **Don't add Qt-dependent logic to core modules** — Keep `src/core/` import-free of PySide6. The codebase already does this well.
- ❌ **Don't bypass theUndoStack** — All timeline edits should go through `TimelinePanel.undo()` / `redo()` which uses `_commit()` → `UndoStack.push()`.
- ❌ **Don't hard-code FFmpeg filter strings** — Always use `FFmpegExporter.build_command()` so filters are consistent and testable.
- ❌ **Don't add new dependencies without need** — The codebase is carefully minimal. Add `numpy` or `librosa` only if waveform quality is a proven bottleneck.
- ❌ **Don't mix serialization formats** — Project files use JSON (`save_project`/`load_project`). Media clips use `MediaClip.to_dict()`/`from_dict()`. Keep it consistent.

### Testing Recommendations

- Run existing tests: `python -m pytest tests/test_core/test_timeline_ops.py` or `python -m unittest discover tests/`
- All core tests are headless and run instantly
- For GUI changes, use `pytest-qt` with QApp headless mode
- Export tests need actual ffmpeg binary — mock or skip in CI

### Build/Packaging Notes

- PyInstaller spec already bundles ffmpeg/ffprobe if present in `bin/` directory
- `.env.hub` is read at startup to resolve binary paths
- `resolve_binary()` searches: explicit path → bundle dir → PATH env
- For Windows packaging, ensure `ffmpeg.exe`/`ffprobe.exe` are in the `bin/` folder or available via PATH
- The `validate_build_inputs()` function checks for required files before build

### Summary

**The codebase is well-structured** with a clear separation between:
- **Core logic** (Qt-free, testable, FFmpeg-wrapped)
- **UI** (PySide6, Qt-dependent)
- **Build/Packaging** (PyInstaller spec + env config)

**Best path forward**: Reuse existing modules extensively. New features should:
1. Add pure-Python functions to `src/core/` (timeline_ops, transitions, audio, timecode)
2. Add FFmpeg wrapper to `src/utils/ffmpeg.py` (FFmpegExporter.build_command)
3. Add UI to `src/ui/panels/` following existing patterns
4. Wire up signals in `src/ui/main_window.py`
5. Test in `tests/test_core/` (headless)
6. Build with PyInstaller using existing spec

This approach keeps development fast, maintains testability, and avoids bloated dependencies while supporting a full desktop NLE experience.

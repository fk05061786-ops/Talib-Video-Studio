# Build and Deployment Instructions

## Windows Build
1. **Prerequisites**: Install Python 3.10+ and FFmpeg (add FFmpeg to Windows PATH).
2. **Setup**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Build**:
   ```bash
   python scripts/build_exe.py
   ```
4. **Output**: The standalone executable and dependencies will be generated in the `dist/TalibVideoStudio` folder.

## Deployment
- Copy the entire `dist/TalibVideoStudio` folder to the target machine.
- Ensure the user has FFmpeg installed (or configure `FFMPEG_PATH` in `.env.hub`).
- Run `TalibVideoStudio.exe` to launch the application.

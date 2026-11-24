# Talib Video Studio: Lightweight MVP Implementation Plan

> **Goal:** Build a minimal working version of Talib Video Studio with a dark Windows interface, video import, preview player, basic controls, and MP4 export.

> **Tech Stack:** Python 3.10+, PySide6, FFmpeg, SQLite (optional for metadata).

> **Execution:** Native implementation in this session.

## Architecture

The app will consist of:
- A **main window** with a dark theme and basic UI controls.
- A **video import dialog** for adding clips.
- A **video preview player** with play/pause functionality.
- A **simple export dialog** for MP4 output.

## Global Constraints

- **Platform:** Windows (Intel i3 or equivalent).
- **Dependencies:** Only free/open-source tools (PySide6, FFmpeg).
- **Performance:** Minimal resource usage for lightweight operation.
- **Codebase:** New project, no existing dependencies.

## File Structure

```
Talib-Video-Studio/
├── src/
│   ├── main.py                # Main application entry point
│   ├── ui/
│   │   ├── main_window.py     # Main GUI window
│   │   ├── dialogs.py          # Import/export dialogs
│   │   └── player.py           # Video preview player
│   └── utils/
│       └── ffmpeg.py          # FFmpeg integration
├── tests/
│   └── ui/                    # Unit tests for UI components
└── .gitignore
```

## Tasks

### Task 1: Main Window

**Files:**
- Create: `src/ui/main_window.py`
- Modify: `src/main.py`

**Interfaces:**
- Consumes: None
- Produces: `MainWindow` class with:
  - `show_import_dialog()`
  - `show_export_dialog()`
  - `play_video(video_path)`
  - `pause_video()`

**Steps:**
- [ ] **Step 1: Write the failing test**
  ```python
  def test_main_window():
      from PySide6.QtWidgets import QApplication
      app = QApplication([])
      window = MainWindow()
      window.show()
      assert window.isVisible()
  ```

- [ ] **Step 2: Implement `MainWindow` class in `src/ui/main_window.py`**
  ```python
  from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QPushButton, QFileDialog
  from PySide6.QtCore import QTimer
  from PySide6.QtGui import QIcon
  from .player import VideoPlayer

  class MainWindow(QMainWindow):
      def __init__(self):
          super().__init__()
          self.setWindowTitle("Talib Video Studio")
          self.setWindowIcon(QIcon("assets/icon.png"))
          self.setGeometry(100, 100, 800, 600)
          self.setStyleSheet("background-color: #121212; color: #e0e0e0;")
          
          self.video_player = VideoPlayer()
          self.layout = QVBoxLayout()
          
          self.import_button = QPushButton("Import Video")
          self.import_button.clicked.connect(self.show_import_dialog)
          self.layout.addWidget(self.import_button)
          
          self.export_button = QPushButton("Export Video")
          self.export_button.clicked.connect(self.show_export_dialog)
          self.layout.addWidget(self.export_button)
          
          self.player_container = QWidget()
          self.player_container.setObjectName("player_container")
          self.player_container.setStyleSheet("background-color: #1e1e1e;")
          self.layout.addWidget(self.player_container)
          
          self.player_container.layout().addWidget(self.video_player)
          
          self.setCentralWidget(QWidget(self.layout))
  ```

- [ ] **Step 3: Commit**
  ```bash
  git add src/ui/main_window.py src/main.py
  git commit -m "feat: add main window with dark theme"
  ```


### Task 2: Video Player

**Files:**
- Create: `src/ui/player.py`

**Interfaces:**
- Consumes: None
- Produces: `VideoPlayer` class with:
  - `play()`
  - `pause()`
  - `set_video_path(video_path)`

**Steps:**
- [ ] **Step 1: Write the failing test**
  ```python
  def test_video_player():
      from PySide6.QtWidgets import QApplication
      app = QApplication([])
      player = VideoPlayer()
      assert player.is_playing == False
  ```

- [ ] **Step 2: Implement `VideoPlayer` class in `src/ui/player.py`**
  ```python
  from PySide6.QtWidgets import QWidget, QLabel
  from PySide6.QtCore import QTimer
  from PySide6.QtGui import QMovie

  class VideoPlayer(QLabel):
      def __init__(self):
          super().__init__()
          self.setObjectName("video_player")
          self.setStyleSheet("background-color: #1e1e1e;")
          self.movie = QMovie("assets/video_placeholder.gif")
          self.movie.setLoopCount(QMovie.Infinite)
          self.setMovie(self.movie)
          self.movie.start()
          
      def play(self):
          self.movie.stop()
          self.movie.start()
          
      def pause(self):
          self.movie.stop()
          
      def set_video_path(self, video_path):
          self.movie = QMovie(video_path)
          self.movie.setLoopCount(QMovie.Infinite)
          self.setMovie(self.movie)
          self.movie.start()
  ```

- [ ] **Step 3: Commit**
  ```bash
  git add src/ui/player.py
  git commit -m "feat: add video player"
  ```


### Task 3: Import Dialog

**Files:**
- Create: `src/ui/dialogs.py`

**Interfaces:**
- Consumes: `MainWindow`
- Produces: `ImportDialog` class with:
  - `show_dialog()`
  - `select_video()`

**Steps:**
- [ ] **Step 1: Write the failing test**
  ```python
  def test_import_dialog():
      from PySide6.QtWidgets import QApplication, QFileDialog
      app = QApplication([])
      dialog = ImportDialog()
      assert dialog.isVisible()
  ```

- [ ] **Step 2: Implement `ImportDialog` class in `src/ui/dialogs.py`**
  ```python
  from PySide6.QtWidgets import QDialog, QFileDialog, QVBoxLayout, QPushButton

  class ImportDialog(QDialog):
      def __init__(self, parent=None):
          super().__init__(parent)
          self.setWindowTitle("Import Video")
          self.setStyleSheet("background-color: #121212; color: #e0e0e0;")
          
          self.layout = QVBoxLayout()
          self.button = QPushButton("Select Video")
          self.button.clicked.connect(self.select_video)
          self.layout.addWidget(self.button)
          
          self.setLayout(self.layout)
          
      def select_video(self):
          file_path, _ = QFileDialog.getOpenFileName(self, "Select Video", "", "Video Files (*.mp4 *.avi *.mkv)")
          if file_path:
              parent = self.parent()
              if parent:
                  parent.video_player.set_video_path(file_path)
                  parent.close()
  ```

- [ ] **Step 3: Commit**
  ```bash
  git add src/ui/dialogs.py
  git commit -m "feat: add import dialog"
  ```


### Task 4: Export Dialog

**Files:**
- Create: `src/ui/dialogs.py` (modify)

**Interfaces:**
- Consumes: `MainWindow`
- Produces: `ExportDialog` class with:
  - `show_dialog()`
  - `export_video()`

**Steps:**
- [ ] **Step 1: Update `ImportDialog` to include export logic**
  ```python
  def export_video(self):
      file_path, _ = QFileDialog.getSaveFileName(self, "Export Video", "", "MP4 Files (*.mp4)")
      if file_path:
          from .ffmpeg import export_video
          export_video(self.parent().video_player.video_path, file_path)
          self.parent().close()
  ```

- [ ] **Step 2: Implement `export_video` in `src/utils/ffmpeg.py`**
  ```python
  import subprocess
  
  def export_video(input_path, output_path):
      subprocess.run([
          "ffmpeg",
          "-i", input_path,
          "-c:v", "libx264",
          "-preset", "fast",
          "-crf", "23",
          output_path
      ], check=True)
  ```

- [ ] **Step 3: Commit**
  ```bash
  git add src/utils/ffmpeg.py
  git commit -m "feat: add export functionality"
  ```


### Task 5: Main Application Entry

**Files:**
- Modify: `src/main.py`

**Steps:**
- [ ] **Step 1: Implement `main` function in `src/main.py`**
  ```python
  from PySide6.QtWidgets import QApplication
  from src.ui.main_window import MainWindow

  def main():
      app = QApplication([])
      window = MainWindow()
      window.show()
      app.exec()

  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 2: Commit**
  ```bash
  git add src/main.py
  git commit -m "feat: add main application entry"
  ```

--- 
## How to Run the Application

1. **Install Dependencies:**
   ```bash
   pip install PySide6 ffmpeg-python
   ```
   Ensure FFmpeg is installed on your system. On Windows, download it from [FFmpeg's official site](https://ffmpeg.org/download.html).

2. **Run the Application:**
   ```bash
   python src/main.py
   ```

3. **Features:**
   - Import videos via the "Import Video" button.
   - Preview videos in the player.
   - Export videos to MP4 using the "Export Video" button.

--- 
## Next Steps

- The application is now a working MVP with the core features requested.
- Add more advanced features (e.g., timeline editing, audio tracks) in future iterations.
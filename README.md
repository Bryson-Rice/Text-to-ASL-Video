# ASL Text to Video
Input text either with OCR or manual entry and output a video of the text in ASL

The program can take input in two ways:

* **Manual text input**
* **OCR screen capture** (select an area of your screen and extract text)

---

# Installation

### 1. Install Python dependencies

```
pip install -r requirements.txt
```

### 2. Install required system tools

You must also install the following:

* [FFmpeg](https://www.ffmpeg.org/download.html) (includes **ffplay** which is used for video playback)
* [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (used for screen text recognition)

Both must be available in your **system PATH**.

---

# Setup

Before running the program, update the `VIDEO_DIR` variable in `main.py` so it points to your ASL video library.

Example:

```
VIDEO_DIR = "C:/path/to/your/asl/videos"
```

---

# ASL Video Files

You must provide your **own ASL video dataset**.

[HandSpeak](https://www.handspeak.com/) has a very large collection of ASL videos, I'm sure you can find a way to download videos from their website or find a premade collection of ASL videos

ASL videos are **not included in this repository** due to **copyright restrictions** that prevent redistribution of the original video sources.

The program expects a folder containing ASL clips named according to the words or phrases they represent.

Example folder structure:

```
asl-videos/
├── hello.mkv
├── thank you.mkv
├── good morning.mkv
├── I.mkv
```

---

# Hotkeys

| Hotkey       | Action                              |
| ------------ | ----------------------------------- |
| **Ctrl + E** | Scan screen and perform OCR         |
| **Ctrl + I** | Manual text input                   |
| **Ctrl + R** | Replay the last generated ASL video |
| **Ctrl + Q** | Quit the application                |


---

# Notes

* The system attempts to find the **best phrase matches** when possible.
* Words without matching videos will be skipped and shown as warnings.
* Videos are temporarily processed and combined before playback.

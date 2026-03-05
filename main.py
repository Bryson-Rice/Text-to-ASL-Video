import cv2
import ffmpeg
import keyboard
import mss
import nltk
import numpy as np
import os
import psutil
import pytesseract
import re
import string
import subprocess
import sys
import tempfile
import time
import win32api
import win32con
import win32gui

from nltk.stem import WordNetLemmatizer
from threading import Thread, Event


VIDEO_DIR = "UPDATE-ME-TO-VIDEO-FOLDER"

nltk.download("wordnet", quiet=True)
nltk.download("omw-1.4", quiet=True)


class AppState:
    def __init__(self):
        self.exit_flag = Event()
        self.last_translation = None


class VideoLibrary:

    def __init__(self, video_dir):
        self.video_dir = video_dir
        self.file_mapping = self._load_videos()

    def _clean_filename(self, filename):
        name = os.path.splitext(filename)[0]
        name = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', name)
        name = name.replace('-', ' ')
        name = name.replace('⧸', '/')
        name = ' '.join(name.split())
        return name

    def _load_videos(self):
        mapping = {}
        for filename in os.listdir(self.video_dir):
            if filename.endswith(('.mkv', '.mp4', '.webm')):
                clean_name = self._clean_filename(filename)
                meanings = [m.strip() for m in re.split(r'[⧸/]', clean_name)]
                for meaning in meanings:
                    if meaning:
                        mapping[meaning.lower()] = filename
        return mapping


class TextProcessor:

    def __init__(self):
        self.lemmatizer = WordNetLemmatizer()

    def get_base_form(self, word):
        word = word.replace("’", "'")
        word = word.strip(string.punctuation)
        singular_word = self.lemmatizer.lemmatize(word, 'n')
        base_word = self.lemmatizer.lemmatize(singular_word, 'v')
        return base_word.lower()

    def find_best_video_matches(self, sentence, file_mapping):

        sentence = sentence.lower()
        single_letter_matches = {"i": "I.mkv"}

        def find_matches(remaining_text, memo=None):

            if memo is None:
                memo = {}

            if not remaining_text:
                return [], [], 0

            if remaining_text in memo:
                return memo[remaining_text]

            best_matches = None
            best_missing = None
            best_score = float('-inf')

            words = remaining_text.split()
            if not words:
                return [], [], 0

            if words[0].lower() in single_letter_matches:
                next_text = " ".join(words[1:])
                next_matches, next_missing, next_score = find_matches(next_text)
                return (
                    [single_letter_matches[words[0].lower()]] + next_matches,
                    next_missing,
                    10 + next_score
                )

            for i in range(len(words)):
                current_phrase = " ".join(words[:i+1])
                if current_phrase in file_mapping:
                    next_text = " ".join(words[i+1:])
                    next_matches, next_missing, next_score = find_matches(next_text)
                    current_score = len(current_phrase.split()) * 10 + next_score
                    if current_score > best_score:
                        best_score = current_score
                        best_matches = [file_mapping[current_phrase]] + next_matches
                        best_missing = next_missing

            if best_matches is None:
                base_word = self.get_base_form(words[0])
                if base_word != words[0] and base_word in file_mapping:
                    next_text = " ".join(words[1:])
                    next_matches, next_missing, next_score = find_matches(next_text)
                    best_matches = [file_mapping[base_word]] + next_matches
                    best_missing = next_missing
                    best_score = next_score
                else:
                    next_text = " ".join(words[1:])
                    next_matches, next_missing, next_score = find_matches(next_text)
                    best_matches = next_matches
                    best_missing = [words[0]] + next_missing
                    best_score = next_score

            memo[remaining_text] = (best_matches, best_missing, best_score)
            return best_matches, best_missing, best_score

        matches, missing, _ = find_matches(sentence)
        return matches, missing


class OCRScanner:

    def __init__(self):
        self.rect_start = None
        self.rect_end = None
        self.selection_done = False

    def reset(self):
        self.rect_start = None
        self.rect_end = None
        self.selection_done = False

    def extract_text(self, region):
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray)
        text = text.translate(str.maketrans('', '', string.punctuation))
        return text.strip()

    def select_region(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.rect_start = (x, y)
            self.rect_end = (x, y)
            self.selection_done = False
        elif event == cv2.EVENT_MOUSEMOVE and self.rect_start:
            self.rect_end = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.rect_end = (x, y)
            self.selection_done = True

    def capture(self):

        hwnd = win32gui.GetForegroundWindow()
        rect = win32gui.GetWindowRect(hwnd)
        win_left, win_top, win_right, win_bottom = rect

        monitors = win32api.EnumDisplayMonitors()
        monitor_bounds = None
        for monitor in monitors:
            _, mon_rect = monitor[0], monitor[2]
            if (win_left < mon_rect[2] and win_right > mon_rect[0] and
                win_top < mon_rect[3] and win_bottom > mon_rect[1]):
                monitor_bounds = mon_rect
                break

        if monitor_bounds is None:
            monitor_bounds = (0, 0, 1920, 1080)

        mon_left, mon_top, mon_right, mon_bottom = monitor_bounds
        width = mon_right - mon_left
        height = mon_bottom - mon_top

        with mss.mss() as sct:
            monitor = {"left": mon_left, "top": mon_top, "width": width, "height": height}
            screenshot = sct.grab(monitor)
            screen_bgr = np.array(screenshot)[:, :, :3]

        cv2.namedWindow("Select Region", cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("Select Region", cv2.WND_PROP_TOPMOST, 1)
        cv2.resizeWindow("Select Region", width, height)
        cv2.setMouseCallback("Select Region", self.select_region)

        while True:
            temp_image = screen_bgr.copy()
            if self.rect_start and self.rect_end:
                cv2.rectangle(temp_image, self.rect_start, self.rect_end, (0, 255, 0), 2)
            cv2.imshow("Select Region", temp_image)

            if self.selection_done:
                break

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cv2.destroyAllWindows()

        if self.rect_start and self.rect_end:
            x1, y1 = self.rect_start
            x2, y2 = self.rect_end
            return screen_bgr[min(y1, y2):max(y1, y2), min(x1, x2):max(x1, x2)]
        return None


class VideoRenderer:

    def __init__(self, video_dir, state: AppState):
        self.video_dir = video_dir
        self.state = state

    def play(self, path):
        subprocess.run(
            [
                "ffplay",
                "-autoexit",
                "-vf",
                "scale='if(lt(ih,720),-2,iw)':'if(lt(ih,720),720,ih)'", #scale to 720p at min
                path
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def render(self, sentence, matches, missing_words):

        if missing_words:
            print(f"\033[91mWarning: Could not find videos for words: {', '.join(missing_words)}\033[0m")

        temp_clips = []

        with tempfile.TemporaryDirectory() as temp_dir:

            for idx, filename in enumerate(matches):
                video_path = os.path.join(self.video_dir, filename)
                intermediate = os.path.join(temp_dir, f"inter_{idx}.mp4")
                output = os.path.join(temp_dir, f"clip_{idx}.mp4")

                (
                    ffmpeg
                    .input(video_path)
                    .output(intermediate,
                            vcodec='libx264',
                            acodec='aac',
                            r=30,
                            preset='medium',
                            loglevel="quiet")
                    .run(overwrite_output=True)
                )

                font_path = "C:/Windows/Fonts/Arial.ttf"

                (
                    ffmpeg
                    .input(intermediate)
                    .filter("drawtext",
                            fontfile=font_path,
                            text=os.path.splitext(filename)[0],
                            fontsize=35,
                            fontcolor="black",
                            bordercolor="white",
                            x=10,
                            y=10,
                            borderw=1)
                    .output(output,
                            vcodec='libx264',
                            acodec='aac',
                            loglevel="quiet")
                    .run(overwrite_output=True)
                )

                temp_clips.append(output)

            if temp_clips:
                final_output = os.path.join(tempfile.gettempdir(), "asl_translation.mp4")
                concat_file = os.path.join(temp_dir, "concat.txt")

                with open(concat_file, "w", encoding="utf-8") as f:
                    for clip in temp_clips:
                        f.write(f"file '{os.path.abspath(clip)}'\n")

                (
                    ffmpeg
                    .input(concat_file, format="concat", safe=0)
                    .output(final_output,
                            vcodec='libx264',
                            acodec='aac',
                            loglevel="quiet")
                    .run(overwrite_output=True)
                )

                self.state.last_translation = final_output
                self.play(final_output)


class ASLTranslatorApp:

    def __init__(self):
        self.state = AppState()
        self.library = VideoLibrary(VIDEO_DIR)
        self.processor = TextProcessor()
        self.ocr = OCRScanner()
        self.renderer = VideoRenderer(VIDEO_DIR, self.state)

    def scan_screen(self):
        print("\nHotkey detected! Starting screen scan...")

        self.ocr.reset()
        region = self.ocr.capture()
        if region is None:
            print("No region selected.")
            return

        text = self.ocr.extract_text(region)
        if text:
            print(f"\033[34mDetected text: {text}\033[0m")
            matches, missing = self.processor.find_best_video_matches(
                text,
                self.library.file_mapping
            )
            self.renderer.render(text, matches, missing)

    def manual_input(self):
        print("\nManual input mode activated. Type your text below:")
        sentence = input("Enter text to translate: ").strip()

        if not sentence:
            print("Please type some text and press Enter.")
            return


        if sentence:
            matches, missing = self.processor.find_best_video_matches(
                sentence,
                self.library.file_mapping
            )
            self.renderer.render(sentence, matches, missing)

    def replay(self):
        if self.state.last_translation:
            print("\nReplaying last translation...")
            self.renderer.play(self.state.last_translation)
        else:
            print("\nNo previous translation found.")

    def run(self):

        keyboard.add_hotkey('ctrl+e', self.scan_screen)
        keyboard.add_hotkey('ctrl+i', self.manual_input)
        keyboard.add_hotkey('ctrl+r', self.replay)
        keyboard.add_hotkey('ctrl+q', lambda: self.state.exit_flag.set())

        print("ASL Translator running in background.")
        print("Hotkeys:")
        print("  Ctrl+E: Scan screen")
        print("  Ctrl+I: Manual text input")
        print("  Ctrl+R: Replay last translation")
        print("  Ctrl+Q: Quit")
        print("ASL Translator running in background. Press Ctrl+E to scan screen, or Ctrl+Q to quit.\n")

        while not self.state.exit_flag.is_set():
            time.sleep(0.1)

        print("\nApplication terminated.")


if __name__ == "__main__":
    ASLTranslatorApp().run()


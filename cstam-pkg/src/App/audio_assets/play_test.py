import pygame
import time
import os

files = [
    "/home/mo/ws/src/App/audio_assets/intro_rafiq.mp3",
    "/home/mo/ws/src/App/audio_assets/yolo_thank_you.mp3"
]

# Initialize with the CORRECT frequency (The Fix)
pygame.mixer.init(frequency=24000)

print("--- Testing Audio Quality (24kHz) ---")

for f in files:
    if os.path.exists(f):
        print(f"Playing: {os.path.basename(f)}")
        pygame.mixer.music.load(f)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        time.sleep(0.5)
    else:
        print(f"File not found: {f}")

print("--- Done ---")

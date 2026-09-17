#!/usr/bin/env python3
import os
from gtts import gTTS
import pygame
def play_text(text):
    print(f"Generating audio for: '{text}'")
    tts = gTTS(text=text, lang='en', slow=False)
    filename = f"/tmp/test_audio_{int(time.time())}.mp3"
    tts.save(filename)
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    print("Playing audio...")
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    os.remove(filename)
    print("Done.\n")
if __name__ == "__main__":
    print("Testing Audio Messages...\n")
    print("1. Arrival Message:")
    play_text("Welcome! I have arrived. Please scan your QR code to receive your order.")
    time.sleep(1)
    print("2. QR Success Message:")
    play_text("QR code verified successfully. Please open the box and take your order. When you are finished, please give me a like.")
    time.sleep(1)
    print("3. YOLO Success Message:")
    play_text("We're so glad your order arrived! Thank you for being a valued customer.")

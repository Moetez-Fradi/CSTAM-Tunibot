#!/usr/bin/env python3
import edge_tts
import pygame
import os
import time
VOICE = "en-US-ChristopherNeural"
MESSAGES = [
    "Welcome. I have arrived at the delivery location. Please present your QR code to verify your identity.",
    "Identity verified successfully. Please retrieve your order from the compartment. Once finished, kindly give a thumbs up to complete the delivery.",
    "Thank you for your feedback. It has been a pleasure serving you. Have a wonderful day."
]
async def stress_test():
    print(f"Testing Voice: {VOICE}\n")
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    for i, text in enumerate(MESSAGES):
        print(f"[{i+1}] {text}")
        filename = f"/tmp/test_v2_{i}.mp3"
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(filename)
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        os.remove(filename)
        time.sleep(1)
if __name__ == "__main__":
    asyncio.run(stress_test())

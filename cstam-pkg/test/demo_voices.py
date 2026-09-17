#!/usr/bin/env python3
import edge_tts
import pygame
import os
import time
VOICES = [
    {"name": "en-US-GuyNeural", "desc": "US Male (Guy)"},
    {"name": "en-US-ChristopherNeural", "desc": "US Male (Christopher)"},
    {"name": "en-GB-RyanNeural", "desc": "UK Male (Ryan)"},
    {"name": "en-GB-ThomasNeural", "desc": "UK Male (Thomas)"},
    {"name": "en-CA-LiamNeural", "desc": "Canadian Male (Liam)"},
    {"name": "en-AU-WilliamMultilingualNeural", "desc": "Australian Male (William)"}
]
TEXT = "Welcome! I have arrived. Please scan your QR code to receive your order."
async def generate_and_play(voice_name, desc):
    print(f"\n--- Generaring: {desc} ({voice_name}) ---")
    communicate = edge_tts.Communicate(TEXT, voice_name)
    filename = f"/tmp/demo_{voice_name}.mp3"
    await communicate.save(filename)
    print(f"Playing...")
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    os.remove(filename)
async def main():
    print("Generating voice samples...")
    for v in VOICES:
        await generate_and_play(v["name"], v["desc"])
        time.sleep(1)
if __name__ == "__main__":
    asyncio.run(main())

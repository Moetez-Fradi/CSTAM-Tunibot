import asyncio
import edge_tts
import pygame
import time
import os

AUDIT_DIR = "/home/mo/ws/src/App/audio_assets/samples"
os.makedirs(AUDIT_DIR, exist_ok=True)

VOICES = [
    ("Guy", "en-US-GuyNeural"),
    ("Christopher", "en-US-ChristopherNeural"),
    ("Eric", "en-US-EricNeural"),
    ("Roger", "en-US-RogerNeural"),
    ("Steffan", "en-US-SteffanNeural")
]

async def generate_and_play():
    if not pygame.mixer.get_init():
        pygame.mixer.init()

    print("--- Starting Voice Audit ---")
    for name, voice_id in VOICES:
        text = f"Hello. I am {name}. This is how I sound."
        filename = os.path.join(AUDIT_DIR, f"{name}.mp3")
        
        print(f"Generating {name}...")
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(filename)
        
        print(f"Playing {name}...")
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        
        time.sleep(1.0) # Pause between voices

    print("--- Audit Complete ---")

if __name__ == "__main__":
    asyncio.run(generate_and_play())

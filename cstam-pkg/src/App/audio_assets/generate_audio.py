import asyncio
import edge_tts
import os

assets_dir = "/home/mo/ws/src/App/audio_assets"
os.makedirs(assets_dir, exist_ok=True)

VOICE = "en-US-GuyNeural"

async def generate():
    # 1. Intro Message (Arrival)
    intro_text = "Hi! I am here. Can you please scan the QR code I sent you?"
    intro_path = os.path.join(assets_dir, "audio_intro.mp3")
    print(f"Generating (Guy): {intro_path}")
    await edge_tts.Communicate(intro_text, VOICE).save(intro_path)

    # 2. Instruction Message (After QR Verification)
    instr_text = "Perfect! Please open the box and take your order. When you are done, please show me a Like sign."
    instr_path = os.path.join(assets_dir, "audio_instruction.mp3")
    print(f"Generating (Guy): {instr_path}")
    await edge_tts.Communicate(instr_text, VOICE).save(instr_path)

    # 3. Thank You Message (After Like Detected)
    thank_text = "Thank you! I am glad I could help. Have a nice day!"
    thank_path = os.path.join(assets_dir, "audio_thankyou.mp3")
    print(f"Generating (Guy): {thank_path}")
    await edge_tts.Communicate(thank_text, VOICE).save(thank_path)

    print("Done! 3 Audio assets generated.")

if __name__ == "__main__":
    asyncio.run(generate())

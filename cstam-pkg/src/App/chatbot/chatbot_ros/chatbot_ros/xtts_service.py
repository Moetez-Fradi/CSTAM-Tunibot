#!/usr/bin/env python3
import sys
import json
import os
import tempfile
import uuid
import torch
from TTS.api import TTS

def main():
    # Disable gradient calculation for inference
    torch.set_grad_enabled(False)
    
    # Check device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    sys.stderr.write(f"[XTTS Service] Initializing on {device}...\n")
    sys.stderr.flush()

    try:
        # Load model explicitly with agreement
        os.environ["COQUI_TOS_AGREED"] = "1"
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        sys.stderr.write("[XTTS Service] Model loaded successfully.\n")
        
        # Determine speaker
        # Using "Ana Florence" as default if available, or first available
        target_speaker = "Ana Florence"
        
        # If possible, verify speaker exists
        # Note: Accessing internal managers might be brittle, but standard names usually work.
        # We will wrap synthesis in try/catch to handle invalid speaker names if needed.
        
        sys.stderr.write(f"[XTTS Service] Ready. Default Speaker: {target_speaker}\n")
        sys.stderr.flush()
        
        # Signal ready to parent process
        print(json.dumps({"status": "ready"}))
        sys.stdout.flush()

    except Exception as e:
        sys.stderr.write(f"[XTTS Service] CRITICAL ERROR loading model: {e}\n")
        sys.stderr.flush()
        sys.exit(1)

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue
                
            req = json.loads(line)
            text = req.get("text", "")
            language = req.get("language", "ar")
            speaker = req.get("speaker", target_speaker)
            
            if not text:
                print(json.dumps({"status": "error", "message": "Empty text"}))
                sys.stdout.flush()
                continue
            
            # Create temp file
            temp_file = os.path.join(tempfile.gettempdir(), f"tts_{uuid.uuid4()}.wav")
            
            # Synthesize (redirect stdout to stderr in case TTS prints anything)
            import contextlib
            with contextlib.redirect_stdout(sys.stderr):
                tts.tts_to_file(
                    text=text,
                    file_path=temp_file,
                    speaker=speaker,
                    language=language
                )
            
            # Respond success
            resp = {
                "status": "success",
                "file_path": temp_file,
                "text": text
            }
            print(json.dumps(resp))
            sys.stdout.flush()

        except json.JSONDecodeError:
            sys.stderr.write("[XTTS Service] Invalid JSON received.\n")
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"[XTTS Service] Error processing request: {e}\n")
            sys.stderr.flush()
            # Send error response
            print(json.dumps({"status": "error", "message": str(e)}))
            sys.stdout.flush()

if __name__ == "__main__":
    main()

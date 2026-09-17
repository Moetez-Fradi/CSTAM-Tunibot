#!/usr/bin/env python3
import cv2
import time
import os
def test_camera():
    print("🔍 Searching for camera...")
    device_path = "/dev/video0"
    for i in range(10):
        path = f"/dev/video{i}"
        if os.path.exists(path):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    cap.release()
                    if ret:
                        print(f"✅ Found working camera at {path}")
                        device_path = path
                        break
            except:
                pass
    idx = int(device_path.replace("/dev/video", ""))
    cap = cv2.VideoCapture(idx)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        print(f"❌ Failed to open {device_path}")
        return
    print(f"🚀 Starting 10-second stability test on {device_path} (MJPEG 640x480)...")
    start_time = time.time()
    frames = 0
    errors = 0
    while time.time() - start_time < 10:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Frame drop / Read error!")
            errors += 1
        else:
            frames += 1
            if frames % 30 == 0:
                print(f"   Running... {frames} frames captured.")
        time.sleep(0.01)
    cap.release()
    duration = time.time() - start_time
    fps = frames / duration
    print("-" * 30)
    print(f"📊 Test Results:")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Frames: {frames}")
    print(f"   Errors: {errors}")
    print(f"   FPS: {fps:.2f}")
    if errors == 0 and frames > 10:
        print("✅ SUCCESS: Camera stream is stable.")
    else:
        print("❌ FAILURE: Stream unstable or disconnected.")
if __name__ == "__main__":
    test_camera()

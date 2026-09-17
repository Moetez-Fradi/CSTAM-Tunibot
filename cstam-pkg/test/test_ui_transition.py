#!/usr/bin/env python3
import cv2
import time
import threading
import numpy as np
def test_transition():
    print("🎥 STARTING SIMULATION: QR Scanner -> YOLO Transition")
    print("---------------------------------------------------")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap = cv2.VideoCapture(1)
        if not cap.isOpened():
            print("❌ No camera found! Cannot simulate.")
            return
    print("✅ Camera Hardware Connected (Simulating ROS connection)")
    print("\n[PHASE 1] QR Scanner Active")
    print("   -> Press 's' to simulate SCAN SUCCESS")
    print("   -> Press 'q' to QUIT simulation immediately")
    scanning = True
    qr_window_name = "QR Scanner Feed (Simulation)"
    while scanning:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Camera frame failed!")
            break
        display = frame.copy()
        cv2.putText(display, "PHASE 1: QR SCANNER", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(display, "Press 's' to Scan", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow(qr_window_name, display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            cap.release()
            cv2.destroyAllWindows()
            return
        elif key == ord('s'):
            print("✅ SCAN SUCCESS TRIGGERED!")
            scanning = False
    print("\n[PHASE 2] Transitioning...")
    print("   -> Closing QR Window...")
    cv2.destroyWindow(qr_window_name) 
    cv2.waitKey(1) 
    print("   -> Waiting 0.5s for cleanup...")
    time.sleep(0.5)
    print("\n[PHASE 3] YOLO Detector Triggered")
    print("   -> Attempting to open YOLO Window...")
    yolo_window_name = "YOLOv8 Like Detection (Simulation)"
    yolo_active = True
    start_time = time.time()
    while yolo_active:
        if time.time() - start_time > 10.0:
            print("Done testing (10s timeout).")
            yolo_active = False
        ret, frame = cap.read()
        if not ret:
             break
        display = frame.copy()
        cv2.putText(display, "PHASE 3: YOLO DETECTOR", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(display, "Smooth Transition!", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        try:
            cv2.imshow(yolo_window_name, display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                yolo_active = False
        except Exception as e:
            print(f"❌ ERROR Showing YOLO Window: {e}")
            yolo_active = False
    print("\n✅ Simulation Complete.")
    print("If you saw the Green 'YOLO' window appear after the Red 'QR' window closed,")
    print("then the fix is VALID.")
    cap.release()
    cv2.destroyAllWindows()
if __name__ == "__main__":
    test_transition()

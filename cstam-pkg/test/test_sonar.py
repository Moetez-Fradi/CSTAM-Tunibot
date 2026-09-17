#!/usr/bin/env python3
import time
PORT = '/dev/ttyACM0'
BAUD = 57600
print(f"📡 Connecting to {PORT} at {BAUD}...")
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print("⏳ Waiting 3 seconds for Arduino to Initialize...")
    time.sleep(3)
    print("\n🦇 Testing Ultrasonic Sensor (10 Readings):")
    print("-" * 40)
    for i in range(10):
        ser.write(b's\r')
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(f"Reading {i+1}: {line} meters")
        else:
            print(f"Reading {i+1}: [No Response]")
        time.sleep(0.5)
    print("-" * 40)
    print("✅ Test Complete. If you saw numbers, it's working!")
    ser.close()
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("Tip: Make sure the port is correct and not used by another program.")

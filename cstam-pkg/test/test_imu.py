#!/usr/bin/env python3
import time
def send_command(ser, cmd):
    print(f"Sending: {cmd}")
    ser.write(f"{cmd}\r".encode())
    time.sleep(1.0)
    response_count = 0
    while ser.in_waiting:
        try:
            line = ser.readline().decode(errors='ignore').strip()
            if line:
                print(f"Received: {line}")
                response_count += 1
        except Exception as e:
            print(f"Error reading line: {e}")
    if response_count == 0:
        print("No response received.")
try:
    print("Opening Serial Port...")
    ser = serial.Serial('/dev/ttyACM0', 57600, timeout=1, rtscts=False, dsrdtr=False)
    print("Resetting Arduino...")
    ser.dtr = False
    time.sleep(0.1)
    ser.dtr = True
    time.sleep(2.0) 
    print("Reading startup messages (I2C Scan)...")
    start_time = time.time()
    while time.time() - start_time < 5.0:
        if ser.in_waiting:
            try:
                line = ser.readline().decode(errors='ignore').strip()
                if line:
                    print(f"Startup: {line}")
            except Exception as e:
                pass
        time.sleep(0.01)
    print("\n--- Testing Data (i) Stress Test (50 iterations) ---")
    start_stress = time.time()
    for _ in range(50):
        ser.write(b"i\r")
        while not ser.in_waiting:
            pass
        line = ser.readline().decode(errors='ignore').strip()
    end_stress = time.time()
    print(f"Stress Test: 50 commands in {end_stress - start_stress:.2f}s (Expected < 1.0s for 50Hz)")
    print("\n--- Testing Sonar (s) ---")
    send_command(ser, 's')
    ser.close()
except Exception as e:
    print(f"Serial Error: {e}")

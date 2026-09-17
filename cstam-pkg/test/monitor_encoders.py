#!/usr/bin/env python3
import time
import sys
def main():
    port = '/dev/ttyACM0'  
    baud = 57600
    try:
        ser = serial.Serial(port, baud, timeout=1)
        print(f"Connected to {port} at {baud} baud.")
    except Exception as e:
        print(f"Error opening port: {e}")
        return
    time.sleep(2)
    print("Reading Encoders (Send 'e'). Move the robot manually!")
    print("Press Ctrl+C to stop.")
    try:
        for i in range(20): 
            ser.write(b'e\r')
            line = ser.readline().decode('utf-8').strip()
            print(f"Encoders: {line}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping.")
    finally:
        ser.close()
if __name__ == "__main__":
    main()

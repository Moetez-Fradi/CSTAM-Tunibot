#!/usr/bin/env python3
import serial
import time
import sys
import serial.tools.list_ports
def get_serial_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None
    target_port = None
    for p in ports:
        print(f"Found port: {p.device} - {p.description}")
        if 'USB' in p.device or 'ACM' in p.device:
            target_port = p.device
    if target_port:
        return target_port
    return ports[0].device
def main():
    port = get_serial_port()
    if not port:
        print("Error: No serial ports found!")
        return
    baud = 57600
    print(f"Connecting to {port} at {baud} baud...")
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2) 
        print("Connected.")
        ser.reset_input_buffer()
        print("Reading Ultrasonic Sensor (Press Ctrl+C to stop)...")
        while True:
            ser.write(b's\r')
            line = ser.readline().decode('utf-8').strip()
            if line:
                print(f"Distance: {line} m")
            else:
                print("No response (Timeout)")
            time.sleep(0.5)
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
if __name__ == '__main__':
    main()

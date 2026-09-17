#!/usr/bin/env python3
p = pyaudio.PyAudio()
info = p.get_host_api_info_by_index(0)
numdevices = info.get('deviceCount')
found = False
for i in range(0, numdevices):
    if (p.get_device_info_by_host_api_device_index(0, i).get('maxOutputChannels')) > 0:
        name = p.get_device_info_by_host_api_device_index(0, i).get('name')
        print(f"Device {i}: {name}")
        if i == 15:
            found = True
if not found:
    print("\nDevice 15 NOT FOUND.")
else:
    print("\nDevice 15 EXISTS.")

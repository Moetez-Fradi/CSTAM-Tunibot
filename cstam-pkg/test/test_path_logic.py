#!/usr/bin/env python3
import datetime
def test_creation():
    now = datetime.datetime.now()
    year_str = now.strftime("%Y")
    month_str = now.strftime("%m")
    day_str = now.strftime("%d")
    mission_time_str = now.strftime("%H%M%S")
    folder_name = f"mission_{mission_time_str}"
    base_dir = os.path.expanduser("~/ws/mission_evidence_TEST") 
    mission_dir = os.path.join(base_dir, year_str, month_str, day_str, folder_name)
    print(f"Attempting to create: {mission_dir}")
    os.makedirs(mission_dir, exist_ok=True)
    if os.path.exists(mission_dir):
        print("SUCCESS: Directory created.")
    else:
        print("FAILURE: Directory not found.")
if __name__ == "__main__":
    test_creation()

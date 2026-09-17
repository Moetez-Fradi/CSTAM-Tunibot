#!/usr/bin/env python3
import pandas as pd
import os
import time
from datetime import datetime
def find_csv_path():
    """
    Attempt to find delivery_log.csv in source directory.
    """
    home = os.path.expanduser("~")
    target_subpath = os.path.join("App", "order_logger", "dashboard", "delivery_log.csv")
    common_workspaces = ["ws", "ros2_ws", "dev_ws", "colcon_ws", "workspace"]
    for ws in common_workspaces:
        candidate = os.path.join(home, ws, "src", target_subpath)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(home, "ws", "src", target_subpath)
CSV_PATH = find_csv_path()
def test_log():
    print(f"📂 Checking Dashboard Log at: {CSV_PATH}")
    if not os.path.exists(CSV_PATH):
        print("❌ CSV File not found! The path is incorrect or file missing.")
        return
    try:
        df = pd.read_csv(CSV_PATH)
        initial_count = len(df)
        print(f"✅ File found. Current Total Orders: {initial_count}")
    except Exception as e:
        print(f"⚠️ Error reading CSV (making new one): {e}")
        df = pd.DataFrame()
        initial_count = 0
    print("✍️ Adding TEST order...")
    test_id = f"TEST_{int(time.time())}"
    now = datetime.now()
    new_row = {
        "Date_Full": now.strftime("%Y-%m-%d"),
        "Year": now.strftime("%Y"),
        "Month": now.strftime("%B"),
        "Day_Name": now.strftime("%A"),
        "Time_Arrival": now.strftime("%H:%M:%S"),
        "Order_ID": test_id,
        "Target_Location": "TEST_LAB",
        "QR_Scan_Status": "Verified",
        "Client_Gesture_Status": "Thumb Up",
        "Handover_Time_Sec": 10,
        "Trip_Duration_Min": 1.5,
        "Distance_Traveled_M": 50.0,
        "Order_Final_Status": "Delivered"
    }
    if df.empty:
        df = pd.DataFrame([new_row])
    else:
        new_df = pd.DataFrame([new_row])
        df = pd.concat([df, new_df], ignore_index=True)
    df.to_csv(CSV_PATH, index=False)
    print(f"✅ Written successfully.")
    print(f"📊 New Total Orders: {len(df)}")
    print("-" * 30)
    print(f"🚀 PLEASE CHECK YOUR DASHBOARD NOW.")
    print(f"You should see Order ID: {test_id}")
    print(f"And specific location: TEST_LAB")
if __name__ == "__main__":
    test_log()

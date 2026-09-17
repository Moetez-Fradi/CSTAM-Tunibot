#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import pandas as pd
import os
import json
from datetime import datetime
class OrderLogger(Node):
    def __init__(self):
        super().__init__('order_logger')
        self.sub_report = self.create_subscription(
            String,
            '/delivery_report',
            self.on_report,
            10
        )
        self.sub_order = self.create_subscription(
            String,
            '/order/json',
            self.on_order_created,
            10
        )
        self.sub_mobile_order = self.create_subscription(
            String,
            '/order/create',
            self.on_order_created,
            10
        )
        self.columns = [
            "Date_Full",
            "Year",
            "Month",
            "Day_Name",
            "Time_Arrival",
            "Order_ID",
            "Target_Location",
            "QR_Scan_Status",
            "Client_Gesture_Status",
            "Handover_Time_Sec",
            "Trip_Duration_Min",
            "Distance_Traveled_M",
            "Order_Final_Status"
        ]
        self.csv_path = self.find_csv_path()
        self.get_logger().info(f'Resolved CSV Path: {self.csv_path}')
        self.get_logger().info(f'Order Logger Ready. Saving/Updating: {self.csv_path}')
    def find_csv_path(self):
        """
        Attempt to find delivery_log.csv in source directory.
        Strategies:
        1. Check if __file__ is symlinked to source (colcon build --symlink-install).
        2. Search common workspace patterns relative to HOME.
        3. Fallback to hardcoded ~/ws/...
        """
        home = os.path.expanduser("~")
        target_subpath = os.path.join("App", "order_logger", "dashboard", "delivery_log.csv")
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            candidate = os.path.abspath(os.path.join(current_dir, "..", "..", "dashboard", "delivery_log.csv"))
            if os.path.exists(os.path.dirname(candidate)): 
                return candidate
        except:
            pass
        common_workspaces = ["ws", "ros2_ws", "dev_ws", "colcon_ws", "workspace"]
        for ws in common_workspaces:
            candidate = os.path.join(home, ws, "src", target_subpath)
            if os.path.exists(candidate):
                return candidate
        return os.path.join(home, "ws", "src", target_subpath)
        self.columns = [
            "Date_Full",
            "Year",
            "Month",
            "Day_Name",
            "Time_Arrival",
            "Order_ID",
            "Target_Location",
            "QR_Scan_Status",
            "Client_Gesture_Status",
            "Handover_Time_Sec",
            "Trip_Duration_Min",
            "Distance_Traveled_M",
            "Order_Final_Status"
        ]
        self.get_logger().info(f'Order Logger Ready. Saving/Updating: {self.csv_path}')
    def on_order_created(self, msg: String):
        """Handle new order: Create 'Pending' entry immediately and setup mission folder."""
        try:
            data = json.loads(msg.data)
            order_id = data.get("order_id")
            if not order_id:
                return

            # --- FILTER RETURN-TO-HOME ORDERS ---
            target_loc = str(data.get("target_location", data.get("address", "N/A"))).strip()
            if target_loc.upper() in ['PKG', 'GARAGE', 'HOME']:
                self.get_logger().info(f"🚫 Ignoring Dashboard Log for Return-to-Base (ID: {order_id}, Target: {target_loc})")
                return
            # ------------------------------------

            self.get_logger().info(f"🆕 New Order detected: {order_id}. Logging initial state...")

            now = datetime.now()
            # target_loc is already extracted above
            row_data = {
                "Date_Full": now.strftime("%Y-%m-%d"),
                "Year": now.strftime("%Y"),
                "Month": now.strftime("%B"),
                "Day_Name": now.strftime("%A"),
                "Time_Arrival": now.strftime("%H:%M:%S"),
                "Order_ID": order_id,
                "Target_Location": target_loc,
                "QR_Scan_Status": "Pending",
                "Client_Gesture_Status": "Pending",
                "Handover_Time_Sec": 0,
                "Trip_Duration_Min": 0.0,
                "Distance_Traveled_M": 0.0,
                "Order_Final_Status": "In Progress"
            }
            self.update_csv(row_data, is_new=True)
        except Exception as e:
            self.get_logger().error(f"Failed to log new order: {e}")
    def on_report(self, msg: String):
        """Handle mission completion: Update existing entry."""
        try:
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                return
            order_id = data.get("order_id")
            if not order_id:
                return
            self.get_logger().info(f"✅ Mission Report for {order_id}. Updating log...")
            now = datetime.now()
            row_data = {
                "Order_ID": order_id, 
                "QR_Scan_Status": data.get("qr_scan_status", "N/A"),
                "Client_Gesture_Status": data.get("client_gesture_status", "N/A"),
                "Handover_Time_Sec": data.get("handover_time_sec", 0),
                "Trip_Duration_Min": data.get("trip_duration_min", 0.0),
                "Distance_Traveled_M": data.get("distance_traveled_m", 0.0),
                "Order_Final_Status": data.get("order_final_status", "Unknown")
            }
            self.update_csv(row_data, is_new=False)
        except Exception as e:
            self.get_logger().error(f"Failed to process report: {e}")
    def update_csv(self, row_data, is_new=True):
        try:
            df = pd.DataFrame()
            if os.path.exists(self.csv_path):
                try:
                    df = pd.read_csv(self.csv_path)
                except Exception:
                    df = pd.DataFrame(columns=self.columns)
            else:
                df = pd.DataFrame(columns=self.columns)
            target_id = row_data.get("Order_ID")
            if is_new:
                if not df.empty and target_id in df['Order_ID'].astype(str).values:
                    self.get_logger().warn(f"Order {target_id} already exists. Skipping creation.")
                    return
                new_df = pd.DataFrame([row_data])
                for col in self.columns:
                    if col not in new_df.columns:
                        new_df[col] = "N/A"
                df = pd.concat([df, new_df[self.columns]], ignore_index=True)
            else:
                if df.empty or target_id not in df['Order_ID'].astype(str).values:
                    self.get_logger().warn(f"Order {target_id} not found for update. Appending as new.")
                    new_df = pd.DataFrame([row_data])
                    for col in self.columns:
                        if col not in new_df.columns:
                            new_df[col] = "N/A"
                    df = pd.concat([df, new_df[self.columns]], ignore_index=True)
                else:
                    idx = df.index[df['Order_ID'].astype(str) == str(target_id)].tolist()[0]
                    for key, val in row_data.items():
                        if key in df.columns:
                            df.at[idx, key] = val
            df.to_csv(self.csv_path, index=False)
            self.get_logger().info(f"💾 CSV Saved. Total records: {len(df)}")
        except Exception as e:
            self.get_logger().error(f"Failed to write CSV: {e}")
def main(args=None):
    rclpy.init(args=args)
    node = OrderLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
if __name__ == '__main__':
    main()

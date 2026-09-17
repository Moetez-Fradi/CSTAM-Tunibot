import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from sensor_msgs.msg import CompressedImage
import json
import os
import threading
import numpy as np
import cv2
import time
import pygame
from typing import Optional

# Check for pyzbar
PYZBAR_AVAILABLE = False
try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False


class QrScanner(Node):
    """
    ROS2 Node for scanning and verifying QR codes.
    
    Workflow:
    1. Listens for user order (on_order_created).
    2. Waits for robot to arrive at destination (on_status -> 'arrived').
    3. Starts scanning camera feed (image_callback).
    4. Decodes QR -> Extracts Payload.
    5. Verifies payload against expected order parameters.
    6. Publishes verification result and plays audio feedback.
    """

    def __init__(self):
        super().__init__('qr_scanner')
        
        # --- Parameters ---
        self.declare_parameter('use_webcam', False)  # Enable laptop webcam for simulation
        self.declare_parameter('scan_timeout', 30.0)
        self.declare_parameter('scan_cooldown', 2.0)
        self.declare_parameter('mission_root_path', os.path.expanduser('~/ws/src/App/order_logger/missions'))
        self.declare_parameter('audio_assets_path', os.path.expanduser('~/ws/src/App/audio_assets'))

        self.simulation_mode = self.get_parameter('use_webcam').get_parameter_value().bool_value
        self.scan_timeout = self.get_parameter('scan_timeout').get_parameter_value().double_value
        self.scan_cooldown = self.get_parameter('scan_cooldown').get_parameter_value().double_value
        self.mission_root = self.get_parameter('mission_root_path').get_parameter_value().string_value
        self.audio_path = self.get_parameter('audio_assets_path').get_parameter_value().string_value
        
        # --- State ---
        self.scanning = False
        self.scan_start_time = 0.0
        self.last_scan_time = 0.0
        self.active_order_id: Optional[str] = None
        self.current_destination: str = "Unknown"
        
        self.mission_qr_scanned = False
        self.mission_yolo_detected = False
        self._frames_processed_count = 0
        
        # --- Audio ---
        try:
            pygame.mixer.init()
            self.get_logger().info("Audio initialized.")
        except Exception as e:
            self.get_logger().error(f"Audio init failed: {e}")

        # --- Publishers ---
        self.pub_scan_result = self.create_publisher(String, '/robot/qr/scanned', 10)
        self.pub_verified = self.create_publisher(Bool, '/robot/qr/verified', 10)
        self.pub_app_goal = self.create_publisher(String, '/app/goal_name', 10) # To send return command
        self.pub_status = self.create_publisher(String, '/robot/qr/scanner_status', 10)
        self.pub_report = self.create_publisher(String, '/delivery_report', 10)
        
        # --- Subscribers ---
        self.sub_order = self.create_subscription(String, '/app/order_created', self.on_order_created, 10)
        self.sub_status = self.create_subscription(String, '/robot/goal_status', self.on_status, 10) # Assuming standard status topic
        self.sub_goal = self.create_subscription(String, '/app/goal_name', self.on_goal_name, 10)
        
        # Camera Subscription (Created on demand or late init)
        self.image_sub = None
        
        # --- Timers & Threads ---
        self._return_timer: Optional[threading.Timer] = None
        
        # Simulation Helpers
        self.sim_cap = None
        self.sim_pub = None
        if self.simulation_mode:
            self._init_simulation_camera()
        else:
            # Auto-detect simulation if /clock exists (optional convenience)
            self.create_timer(2.0, self._auto_detect_sim)

        self.get_logger().info("QrScanner Node Initialized.")


    def _init_simulation_camera(self):
        """Initialize webcam for simulation mode."""
        try:
            self.sim_cap = cv2.VideoCapture(0)
            if self.sim_cap.isOpened():
                self.sim_pub = self.create_publisher(CompressedImage, '/camera/image_raw/compressed', 10)
                self.create_timer(0.05, self._publish_sim_frame) # ~20 FPS
                self.get_logger().info("Simulation Mode: Webcam Capture Started.")
            else:
                self.get_logger().error("Simulation Mode: Could not open webcam.")
        except Exception as e:
            self.get_logger().error(f"Sim Cam Error: {e}")

    def _auto_detect_sim(self):
        """Check if we are in simulation (e.g., /clock exists) and enable webcam if so."""
        if self.simulation_mode: 
            return # Already enabled
            
        topic_list = [t[0] for t in self.get_topic_names_and_types()]
        if '/clock' in topic_list:
            self.get_logger().info("Detected /clock. Switching to Simulation Mode (Webcam).")
            self.simulation_mode = True
            self._init_simulation_camera()

    def _publish_sim_frame(self):
        """Read webcam and publish to /camera/image_raw/compressed."""
        if self.sim_cap and self.sim_cap.isOpened():
            ret, frame = self.sim_cap.read()
            if ret:
                msg = CompressedImage()
                msg.format = "jpeg"
                msg.data = np.array(cv2.imencode('.jpg', frame)[1]).tobytes()
                self.sim_pub.publish(msg)

    # --- Callbacks ---

    def on_order_created(self, msg: String):
        """Handle new order: Parse ID, reset state."""
        try:
            data = json.loads(msg.data)
            self.active_order_id = str(data.get('order_id', '')).strip()
            self.get_logger().info(f"New Order Received: {self.active_order_id}")
            
            # Reset verification state
            self.mission_qr_scanned = False
            self.mission_yolo_detected = False 
            self._cancel_return_timer()
            
        except Exception:
            # Fallback for plain string if needed
            pass

    def on_goal_name(self, msg: String):
        self.current_destination = msg.data.strip()

    def on_status(self, msg: String):
        """If robot arrives, start scanning."""
        try:
            # Flexible parsing: Check for 'arrived' or 'succeeded' keywords
            payload = msg.data.lower()
            is_arrived = 'arrived' in payload or 'succeeded' in payload
            
            if is_arrived and not self.scanning and self.active_order_id:
                if self.current_destination == 'PKG':
                    return # Don't scan at home base
                
                self.start_scanning()
                
            elif not is_arrived and self.scanning:
                # Robot left destination? Stop scanning.
                self.stop_scanning()
                
        except Exception as e:
            self.get_logger().warn(f"Status parse error: {e}")

    # --- Scanning Logic ---

    def start_scanning(self):
        if self.scanning: return
        
        self.scanning = True
        self.scan_start_time = time.time()
        self.get_logger().info("Starting QR Scanner...")
        self._play_audio("intro.mp3") # 'Please show your QR code'
        
        # Subscribe to camera if not already
        if self.image_sub is None:
            self.image_sub = self.create_subscription(
                CompressedImage, '/camera/image_raw/compressed', self.image_callback, 10
            )

    def stop_scanning(self):
        self.scanning = False
        self.get_logger().info("Stopping QR Scanner.")
        # We can keep subscription open or close it. Keeping it open is simpler.
        cv2.destroyAllWindows()
        
        # If we failed to scan, maybe schedule return anyway?
        if not self.mission_qr_scanned:
            self._schedule_return(5.0)

    def image_callback(self, msg):
        if not self.scanning: return
        
        # Timeout Check
        if time.time() - self.scan_start_time > self.scan_timeout:
            self.get_logger().warn("Scan Timed Out.")
            self._play_audio("timeout.mp3")
            self.stop_scanning()
            return

        # Decode Image
        frame = self._imgmsg_to_cv2(msg)
        if frame is None: return
        
        # Process every few frames to save CPU?
        self._frames_processed_count += 1
        
        # Visualization
        display_frame = frame.copy()
        cv2.putText(display_frame, "SCANNING FOR QR...", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Robot QR Scanner", display_frame)
        cv2.waitKey(1)
        
        # Cooldown Check
        if time.time() - self.last_scan_time < self.scan_cooldown:
            return

        # QR Detection
        if PYZBAR_AVAILABLE:
            decoded_objects = pyzbar.decode(frame)
            for obj in decoded_objects:
                payload = obj.data.decode("utf-8")
                self._handle_scanned_payload(payload, frame)
                break # Handle one at a time

    def _handle_scanned_payload(self, payload: str, frame):
        """Verify the scanned payload."""
        self.last_scan_time = time.time()
        self.get_logger().info(f"Scanned Payload: {payload}")
        
        valid = False
        try:
            # Expecting JSON: {"uid": "...", "oid": "ORDER_ID"}
            data = json.loads(payload)
            scanned_oid = str(data.get('oid', '')).strip()
            
            if scanned_oid == self.active_order_id:
                valid = True
            else:
                self.get_logger().warn(f"Order ID Mismatch: Scanned {scanned_oid} vs Active {self.active_order_id}")
        except json.JSONDecodeError:
            # Fallback (legacy): Verify if payload matches order_id directly
            if payload.strip() == self.active_order_id:
                valid = True
        
        self.pub_scan_result.publish(String(data=payload))
        self.pub_verified.publish(Bool(data=valid))
        
        if valid:
            self.get_logger().info("✅ Verification SUCCESS")
            self._play_audio("success.mp3") # 'Verified, thank you'
            self.mission_qr_scanned = True
            
            # Save Evidence
            self._save_evidence(frame)
            
            self.stop_scanning()
            self._schedule_return(5.0)

    def _save_evidence(self, frame):
        """Save the successful scan frame to the mission folder."""
        if not self.active_order_id: return
        
        try:
            folder = os.path.join(self.mission_root, f"mission_{self.active_order_id}")
            if not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
                
            path = os.path.join(folder, "qr_scan_evidence.jpg")
            cv2.imwrite(path, frame)
            self.get_logger().info(f"Evidence saved to {path}")
        except Exception as e:
            self.get_logger().error(f"Failed to save evidence: {e}")

    def _schedule_return(self, delay: float):
        """Schedule the robot to go back to base (PKG)."""
        self._cancel_return_timer()
        
        def _do_return():
            msg = String()
            msg.data = 'PKG'
            self.pub_app_goal.publish(msg)
            self.get_logger().info("Returning to PKG (Home).")
            # Publish Final Report
            self._publish_report()
            
        self._return_timer = threading.Timer(delay, _do_return)
        self._return_timer.start()

    def _cancel_return_timer(self):
        if self._return_timer:
            self._return_timer.cancel()
            self._return_timer = None

    def _publish_report(self):
        """Publish delivery report."""
        report = {
            "order_id": self.active_order_id,
            "qr_verified": self.mission_qr_scanned,
            "timestamp": time.time()
        }
        self.pub_report.publish(String(data=json.dumps(report)))

    # --- Helpers ---

    def _imgmsg_to_cv2(self, img_msg):
        try:
            np_arr = np.frombuffer(img_msg.data, np.uint8)
            return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            self.get_logger().error(f"Img Transform Error: {e}")
            return None

    def _play_audio(self, filename: str):
        """Play audio file in a separate thread."""
        def _job():
            path = os.path.join(self.audio_path, filename)
            if os.path.exists(path):
                try:
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                except Exception as e:
                    self.get_logger().error(f"Audio Playback Error: {e}")
            else:
                self.get_logger().error(f"Audio file missing: {path}")

        threading.Thread(target=_job, daemon=True).start()

    def destroy_node(self):
        self._cancel_return_timer()
        if self.sim_cap:
            self.sim_cap.release()
        cv2.destroyAllWindows()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = QrScanner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

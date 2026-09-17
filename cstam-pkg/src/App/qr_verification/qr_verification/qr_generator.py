import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import os
import json
import uuid
import qrcode
from datetime import datetime
from PIL import Image, ImageDraw

class QrGenerator(Node):
    """
    ROS2 Node that generates QR codes for delivery verification.
    
    Subscribes to:
        - /app/qr/generate (String): Trigger to generate a QR for an order.
        - /app/goal_name (String): Tracks robot location to enable/disable generation (must leave R403).
    
    Publishes to:
        - /app/qr/image (String): Path to the generated QR code image.
    
    Parameters:
        - mission_root (string): Directory to store mission-specific folders. Default: ~/ws/src/App/order_logger/missions
        - order_history_path (string): Path to order history file. Default: ~/ws/src/App/order_logger/dashboard/order_history.txt
    """

    def __init__(self):
        super().__init__('qr_generator')

        # --- Parameters ---
        self.declare_parameter('mission_root', os.path.expanduser('~/ws/src/App/order_logger/missions'))
        self.declare_parameter('order_history_path', os.path.expanduser('~/ws/src/App/order_logger/dashboard/order_history.txt'))
        
        self.mission_root = self.get_parameter('mission_root').get_parameter_value().string_value
        self.order_history_file = self.get_parameter('order_history_path').get_parameter_value().string_value
        
        # --- State ---
        self.previous_location = 'R403'
        self.current_location = 'R403'
        self.has_moved_from_R403 = False
        
        # --- Publishers & Subscribers ---
        self.sub_generate = self.create_subscription(
            String, '/app/qr/generate', self.on_generate, 10
        )
        self.pub_image = self.create_publisher(String, '/app/qr/image', 10)
        self.sub_goal_name = self.create_subscription(
            String, '/app/goal_name', self.on_goal_name, 10
        )
        
        # --- Setup ---
        self._ensure_directories()
        self.get_logger().info(f'QrGenerator Ready. Order History: {self.order_history_file}')

    def _ensure_directories(self):
        """Ensure necessary directories exist."""
        try:
            if not os.path.exists(self.mission_root):
                os.makedirs(self.mission_root, exist_ok=True)
            
            history_dir = os.path.dirname(self.order_history_file)
            if not os.path.exists(history_dir):
                os.makedirs(history_dir, exist_ok=True)
        except Exception as e:
            self.get_logger().error(f"Failed to create directories: {e}")

    def on_goal_name(self, msg: String):
        """Track robot location changes to detect movement from R403."""
        try:
            goal_name = msg.data.strip()
            if not goal_name:
                return
            
            self.previous_location = self.current_location
            self.current_location = goal_name
            
            if self.previous_location == 'R403' and self.current_location != 'R403':
                self.has_moved_from_R403 = True
                self.get_logger().info(f'Left R403 -> {self.current_location}. QR Generation Enabled.')
            elif self.current_location == 'R403':
                self.has_moved_from_R403 = False
                self.get_logger().info('Returned to R403. QR Generation Disabled.')
                
        except Exception as e:
            self.get_logger().error(f'Error tracking location: {e}')

    def on_generate(self, msg: String):
        """
        Generate a QR code upon request.
        Request expected format: JSON string with {"order_id": "...", "address": "..."}
        """
        try:
            req = json.loads(msg.data) if msg.data else {}
            address = req.get('address', 'Unknown')
            order_id = str(req.get('order_id', '')).strip()
            
            if not order_id:
                # If no ID provided, try to generate one (though usually ID should come from order)
                # For safety, we log warning but proceed with a UUID if strictly needed, 
                # but better to rely on input.
                self.get_logger().warn("Received QR generation request without order_id.")
                return

            if not self.has_moved_from_R403:
                self.get_logger().warn(f"Ignored QR request for {order_id}: Robot has not left R403.")
                return

            # Generate Unique QR Payload
            # Format: 16-char short UUID
            unique_payload = str(uuid.uuid4().hex)[:16]
            
            # Create Mission Folder
            folder_name = f"mission_{order_id}"
            mission_dir = os.path.join(self.mission_root, folder_name)
            os.makedirs(mission_dir, exist_ok=True)
            
            # Generate QR Image
            filename = f"qr_{order_id}.png"
            filepath = os.path.join(mission_dir, filename)
            
            if self._create_qr_image(unique_payload, order_id, filepath):
                # Publish Result
                out_msg = String()
                out_msg.data = filepath
                self.pub_image.publish(out_msg)
                
                # Log to History
                self._log_to_order_history(order_id, address, int(datetime.now().timestamp()), filename, filepath)
                self.get_logger().info(f"Generated QR for Order {order_id} at {filepath}")
            else:
                self.get_logger().error(f"Failed to generate QR image for {order_id}")

        except Exception as e:
            self.get_logger().error(f"QR Generation Error: {e}")

    def _create_qr_image(self, payload: str, label_text: str, filepath: str) -> bool:
        """
        Create a QR code image with embedded text/logo.
        Returns: True if successful, False otherwise.
        """
        try:
            # Create basic QR
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            # Payload encapsulates UID and OrderID
            data_to_encode = json.dumps({"uid": payload, "oid": label_text})
            qr.add_data(data_to_encode)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            
            # Optional: Add white box in center for potential logo or just style
            # This mimics previous logic but simplifies it to avoid external dependency for now unless needed.
            # If we want a logo, we could load it if exists.
            
            img.save(filepath)
            return True
        except Exception as e:
            self.get_logger().error(f"Image creation failed: {e}")
            return False

    def _log_to_order_history(self, order_id: str, address: str, timestamp: int, filename: str, filepath: str):
        """Append entry to the central order history file."""
        try:
            dt_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            entry = (
                f"{'='*50}\n"
                f"Order ID: {order_id}\n"
                f"Address: {address}\n"
                f"Time: {dt_str}\n"
                f"File: {filepath}\n"
                f"{'='*50}\n"
            )
            with open(self.order_history_file, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception as e:
            self.get_logger().error(f"History logging failed: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = QrGenerator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

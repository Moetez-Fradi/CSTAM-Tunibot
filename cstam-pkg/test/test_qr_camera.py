#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
import cv2
import numpy as np
import sys
try:
    from pyzbar import pyzbar
    USE_PYZBAR = True
except ImportError:
    USE_PYZBAR = False
class ManualQRTest(Node):
    def __init__(self):
        super().__init__('manual_qr_test')
        self.subscription = self.create_subscription(
            CompressedImage,
            '/camera/image_raw/compressed',
            self.listener_callback,
            10)
        self.get_logger().info('📷 Waiting for camera images on /camera/image_raw/compressed ...')
        self.get_logger().info('Please show a QR code to the camera.')
        self.valid_frames = 0
        if USE_PYZBAR:
            self.get_logger().info(f'✅ Using PYZBAR for decoding (Robust)')
        else:
            self.get_logger().warn(f'⚠️ PYZBAR not found. Using OpenCV detector (Weak). Install pyzbar for better results.')
    def listener_callback(self, msg):
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is None:
                self.get_logger().warn("Received empty image!")
                return
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            decoded_text = None
            detector_name = "None"
            if USE_PYZBAR:
                for img_pass in [gray, enhanced, frame]:
                    decoded_objects = pyzbar.decode(img_pass)
                    if decoded_objects:
                        decoded_text = decoded_objects[0].data.decode('utf-8')
                        detector_name = "Pyzbar"
                        break
            else:
                detector = cv2.QRCodeDetector()
                data, bbox, _ = detector.detectAndDecode(gray)
                if data:
                    decoded_text = data
                    detector_name = "OpenCV"
            if decoded_text:
                print(f"\n✅ QR CODE FOUND [{detector_name}]: {decoded_text}")
                print("-" * 40)
            else:
                print(".", end="", flush=True)
                if self.valid_frames % 30 == 0:
                    h, w = frame.shape[:2]
                    cv2.rectangle(frame, (w//4, h//4), (3*w//4, 3*h//4), (0, 255, 0), 2)
                    cv2.putText(frame, f"{w}x{h} frames={self.valid_frames}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.imwrite('debug_view.jpg', frame)
                    print(f" [Snapshot saved {w}x{h}] ", end="")
            self.valid_frames += 1
        except Exception as e:
            self.get_logger().error(f"Error processing image: {e}")
def main(args=None):
    rclpy.init(args=args)
    tester = ManualQRTest()
    try:
        rclpy.spin(tester)
    except KeyboardInterrupt:
        pass
    tester.destroy_node()
    rclpy.shutdown()
if __name__ == '__main__':
    main()

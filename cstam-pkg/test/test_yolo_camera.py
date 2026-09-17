#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from ament_index_python.packages import get_package_share_directory
import os
import cv2
import numpy as np
import onnxruntime as ort
import yaml
import sys
class YoloTest(Node):
    def __init__(self):
        super().__init__('yolo_test')
        self.subscription = self.create_subscription(
            CompressedImage,
            '/camera/image_raw/compressed',
            self.listener_callback,
            10)
        try:
            pkg_share_dir = get_package_share_directory('yolo_like_detector')
            self.model_path = os.path.join(pkg_share_dir, 'weights', 'best.onnx')
            yaml_path = os.path.join(pkg_share_dir, 'config', 'data.yaml')
            self.get_logger().info(f"Loading Model: {self.model_path}")
            if not os.path.exists(self.model_path):
                self.get_logger().error(f"Model not found at {self.model_path}")
                sys.exit(1)
            self.class_names = ['like'] 
            if os.path.exists(yaml_path):
                with open(yaml_path, 'r') as f:
                    data = yaml.safe_load(f)
                    names = data.get('names', [])
                    if isinstance(names, dict):
                        self.class_names = list(names.values())
                    else:
                        self.class_names = names
            self.session = ort.InferenceSession(self.model_path)
            self.input_name = self.session.get_inputs()[0].name
            self.input_shape = self.session.get_inputs()[0].shape
            self.output_names = [out.name for out in self.session.get_outputs()]
            self.img_height = self.input_shape[2]
            self.img_width = self.input_shape[3]
            self.confidence_threshold = 0.5
            self.get_logger().info(f"YOLO Ready. Input: {self.input_shape}. Waiting for images...")
        except Exception as e:
            self.get_logger().error(f"Failed to init YOLO: {e}")
            sys.exit(1)
        self.valid_frames = 0
    def preprocess_image(self, image):
        img_resized = cv2.resize(image, (self.img_width, self.img_height))
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_normalized = img_rgb.astype(np.float32) / 255.0
        img_transposed = np.transpose(img_normalized, (2, 0, 1))
        img_batch = np.expand_dims(img_transposed, axis=0)
        return img_batch
    def postprocess_detections(self, outputs, original_shape):
        output = outputs[0]
        if len(output.shape) == 3:
            output = output[0].T
        else:
            output = output.T
        detections = []
        orig_height, orig_width = original_shape[:2]
        for pred in output:
            x_center, y_center, width, height = pred[:4]
            class_scores = pred[4:]
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id])
            if confidence < self.confidence_threshold:
                continue
            x1 = int((x_center - width / 2) * orig_width / self.img_width)
            y1 = int((y_center - height / 2) * orig_height / self.img_height)
            x2 = int((x_center + width / 2) * orig_width / self.img_width)
            y2 = int((y_center + height / 2) * orig_height / self.img_height)
            class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"
            detections.append({
                'bbox': [x1, y1, x2, y2],
                'confidence': confidence,
                'class_name': class_name
            })
        return detections
    def listener_callback(self, msg):
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is None:
                return
            input_tensor = self.preprocess_image(frame)
            outputs = self.session.run(self.output_names, {self.input_name: input_tensor})
            detections = self.postprocess_detections(outputs, frame.shape)
            found = False
            for det in detections:
                found = True
                x1, y1, x2, y2 = det['bbox']
                label = f"{det['class_name']} {det['confidence']:.2f}"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                print(f"\n🚀 DETECTED: {label}")
            if not found:
                print(".", end="", flush=True)
            if self.valid_frames % 20 == 0:
                 cv2.putText(frame, f"Frames: {self.valid_frames}", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
                 cv2.imwrite('debug_yolo.jpg', frame)
                 if self.valid_frames % 100 == 0:
                     print(f" [Saved debug_yolo.jpg]", end="")
            self.valid_frames += 1
        except Exception as e:
            self.get_logger().error(f"Inference Error: {e}")
def main(args=None):
    rclpy.init(args=args)
    tester = YoloTest()
    try:
        rclpy.spin(tester)
    except KeyboardInterrupt:
        pass
    tester.destroy_node()
    rclpy.shutdown()
if __name__ == '__main__':
    main()

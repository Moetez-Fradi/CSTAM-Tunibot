#!/usr/bin/env python3
"""
Chat Bridge Node - Connects Mobile App to Llama AI
Subscribes: /app/chat/request (std_msgs/String)
Publishes:  /app/chat/response (std_msgs/String)
Uses:       /llama/generate_response action
            /say action (TTS)
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String, Bool
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import json
from sensor_msgs.msg import LaserScan, CompressedImage
from visualization_msgs.msg import MarkerArray # For reading map labels
import base64
import math
import pandas as pd
import os
import time
import datetime
import datetime
import uuid
import re

# Try to import Audio Common for TTS
try:
    from audio_common_msgs.action import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# Try to import llama_msgs
try:
    from llama_msgs.action import GenerateResponse
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False


class ChatBridge(Node):
    def __init__(self):
        unique_id = str(uuid.uuid4())[:8]
        super().__init__(f'chat_bridge_{unique_id}')
        
        # Publisher for responses
        self.response_pub = self.create_publisher(String, '/app/chat/response', 10)
        
        # Subscriber for requests
        self.request_sub = self.create_subscription(
            String, '/app/chat/request', self.on_request, 10)
        
        # Publisher for detailed status (Mobile Dashboard)
        self.status_pub = self.create_publisher(String, '/app/status', 10)
        self.status_timer = self.create_timer(1.0, self.publish_status) # 1Hz
        
        # Resolve CSV Path Dynamically (Relative to this script)
        # Works for any user/workspace structure as long as packages are in 'src'
        # Resolve CSV Path - Standard 'ws' workspace convention (Requested by User)
        self.csv_path = os.path.expanduser('~/ws/src/App/order_logger/dashboard/delivery_log.csv')
        self.get_logger().info(f"Stats CSV Path: {self.csv_path}")
        
        # Robot State variables
        
        # Robot State variables
        self.current_speed = 0.0
        self.current_location = "Idle"
        self.last_goal_name = "Unknown"
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        
        # Subscribe to Goal Status for Arrival Notifications
        self.goal_status_sub = self.create_subscription(
            String, '/app/goal_status', self.on_goal_status, 10
        )
        
        # TTS Action Client
        if TTS_AVAILABLE:
            self.tts_client = ActionClient(self, TTS, '/say')
            self.get_logger().info('TTS Support Enabled')
        else:
            self.tts_client = None
            self.get_logger().warn('TTS msgs not found - Voice disabled')

        # Llama action client
        if LLAMA_AVAILABLE:
            self.llama_client = ActionClient(
                self, GenerateResponse, '/llama/generate_response')
            self.get_logger().info('Chat Bridge started with Llama AI support')
        else:
            self.llama_client = None
            self.get_logger().warn('Llama msgs not found - using echo mode')
        
        self.get_logger().info('Chat Bridge ready: /app/chat/request -> Llama -> /app/chat/response')
        
        # VISUAL SENSES
        self.latest_vision = "Nothing detected yet"
        self.vision_sub = self.create_subscription(String, '/yolo/detections_str', self.on_vision, 10)
        
        # Camera Snapshot
        self.latest_image = None
        self.image_sub = self.create_subscription(
            CompressedImage, 
            '/camera/image_raw/compressed', 
            self.on_image, 
            10
        )
        
        # COMMAND OUTPUT
        self.cmd_pub = self.create_publisher(String, '/app/goal_name', 10)  # For orders (from app)
        self.direct_nav_pub = self.create_publisher(String, '/app/direct_nav', 10)  # For chatbot navigation (no order)
        self.vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # LIDAR Safety
        self.latest_scan = None
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self.on_scan, 10)
        self.OBSTACLE_THRESHOLD = 0.5  # meters - stop if obstacle closer than this
        
        # Streaming response accumulator
        self._accumulated_response = ""
        self._is_generating = False
        
        # Bridge Waypoints from goal_name.py node
        self.waypoints_pub = self.create_publisher(String, '/app/map/waypoints', 10)
        
        # QoS to match goal_name's TransientLocal (Latched)
        marker_qos = QoSProfile(depth=1)
        marker_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        marker_qos.reliability = QoSReliabilityPolicy.RELIABLE

        self.marker_sub = self.create_subscription(
            MarkerArray, 
            '/named_poses/markers', 
            self.on_map_markers, 
            10  # Changed to standard QoS 10 to accept both VOLATILE and TRANSIENT_LOCAL
        )
        
        # PERSISTENCE: Cache waypoints and republish periodically
        self.cached_waypoints_msg = None
        self.waypoints_timer = self.create_timer(2.0, self.publish_cached_waypoints)

    def on_vision(self, msg: String):
        self.latest_vision = msg.data

    def on_image(self, msg: CompressedImage):
        """Store the latest compressed image msg."""
        self.latest_image = msg

    def on_goal_status(self, msg: String):
        """Handle goal updates to trigger voice notifications."""
        status = msg.data 
        
        if status.startswith("sending:"):
            self.last_goal_name = status.split(":", 1)[1]
            # Debug to chat
            # self.publish_response(f"Refusing to fail silently. Tracking: {self.last_goal_name}")
            self.get_logger().info(f"Tracking goal: {self.last_goal_name}")
            
        elif status == "succeeded":
            self.get_logger().info("Goal succeeded! Triggering arrival notification.")
            arrival_msg = f"I have arrived at {self.last_goal_name}. Waiting for order verification."
            # Force publish
            self.publish_response(arrival_msg)
            # self.speak(arrival_msg) # Actually we rely on app TTS for chat responses
            
        elif status == "not_found":
            self.publish_response(f"I could not find the location {self.last_goal_name}.")

    def execute_command(self, response_text):
        # 2. MOTION (Move Forward, Stop, etc)
        # Initialize action variable here to be used by both detections
        action = None

        # 1. NAVIGATION (Go to X)
        if "[COMMAND:" in response_text:
            try:
                start = response_text.find("[COMMAND:") + 9
                end = response_text.find("]", start)
                if end != -1:
                    cmd_val = response_text[start:end].strip()
                    
                    # CORRECTION: Check if LLM confused COMMAND with ACTION
                    motion_keywords = ["FORWARD", "BACKWARD", "LEFT", "RIGHT", "STOP"]
                    if cmd_val.upper() in motion_keywords:
                        self.get_logger().info(f"🔄 Redirecting COMMAND:{cmd_val} to MOTION logic")
                        action = cmd_val.upper()
                    else:
                        # Real Navigation Command - Use direct_nav (no order)
                        self.get_logger().info(f"🤖 NAV CMD (Direct): Go to {cmd_val}")
                        self.current_location = f"Going to {cmd_val}" 
                        msg = String()
                        msg.data = cmd_val
                        self.direct_nav_pub.publish(msg)  # No order creation
                        
                        return True
            except Exception as e:
                self.get_logger().error(f"Nav parsing error: {e}")

        # 2. MOTION (Move Forward, Stop, etc)
        try:
            # action variable is already initialized at top of function
            pass
            
            # Check standard format [ACTION: XXX]
            if "[ACTION:" in response_text:
                try:
                    start = response_text.find("[ACTION:") + 8
                    end = response_text.find("]", start)
                    if end != -1:
                        action = response_text[start:end].strip().upper()
                except:
                    pass
            
            # Fallback: Check if message STARTS with motion keyword
            if not action:
                upper_resp = response_text.upper()
                if upper_resp.startswith("FORWARD"): action = "FORWARD"
                elif upper_resp.startswith("BACKWARD"): action = "BACKWARD"
                elif upper_resp.startswith("LEFT"): action = "LEFT"
                elif upper_resp.startswith("RIGHT"): action = "RIGHT"
                elif upper_resp.startswith("STOP"): action = "STOP"
                
                # Follow Commands
                # Removed
                
                # Arabic Fallback
                elif response_text.startswith("تحرك"): action = "FORWARD"
                elif response_text.startswith("إرجع") or response_text.startswith("ارجع"): action = "BACKWARD"
                elif response_text.startswith("يمين") or response_text.startswith("لف يمين"): action = "RIGHT"
                elif response_text.startswith("يسار") or response_text.startswith("لف يسار"): action = "LEFT"
                elif response_text.startswith("توقف") or response_text.startswith("قف"): action = "STOP"

            if action:
                self.get_logger().info(f"🤖 MOTION CMD: {action}")
                
                # SAFETY CHECK: Check LIDAR before moving
                obstacle_warning = self.check_obstacle(action)
                if obstacle_warning:
                    self.get_logger().warn(f"⚠️ Motion blocked: {obstacle_warning}")
                    self.publish_response(f"⚠️ Cannot move! {obstacle_warning}")
                    return True
                
                twist = Twist()
                if action == "FORWARD":
                    twist.linear.x = 0.2
                elif action == "BACKWARD":
                    twist.linear.x = -0.2
                elif action == "LEFT":
                    twist.angular.z = 0.5
                elif action == "RIGHT":
                    twist.angular.z = -0.5
                elif action == "STOP":
                    twist.linear.x = 0.0
                    twist.angular.z = 0.0
                    self.current_location = "Stopped"
                
                # Update status
                self.current_speed = abs(twist.linear.x)
                
                # Publish a burst to ensure movement
                for _ in range(5):
                    self.vel_pub.publish(twist)
                    time.sleep(0.1)
                    
                return True
        except Exception as e:
            self.get_logger().error(f"Motion parsing error: {e}")
            return False
        
        return False

    def on_scan(self, msg: LaserScan):
        """Store latest LIDAR scan data."""
        self.latest_scan = msg

    def check_obstacle(self, action: str):
        """
        Check LIDAR for obstacles in the direction of movement.
        Returns warning message if obstacle detected, None if safe to move.
        """
        if self.latest_scan is None:
            return None  # No LIDAR data yet, allow movement
        
        scan = self.latest_scan
        num_readings = len(scan.ranges)
        
        if num_readings == 0:
            return None
        
        # Define angle ranges for each direction (in terms of array indices)
        # Assuming 360 degree LIDAR with readings from -180 to +180 degrees
        # Index 0 = directly behind, num_readings/2 = directly ahead
        
        front_start = int(num_readings * 0.4)  # ~144 degrees to right
        front_end = int(num_readings * 0.6)    # ~216 degrees to left
        back_start = 0
        back_end = int(num_readings * 0.1)
        back_start2 = int(num_readings * 0.9)
        left_start = int(num_readings * 0.6)
        left_end = int(num_readings * 0.75)
        right_start = int(num_readings * 0.25)
        right_end = int(num_readings * 0.4)
        
        def check_range(start, end):
            """Check if any reading in range is below threshold."""
            for i in range(start, end):
                if i < len(scan.ranges):
                    r = scan.ranges[i]
                    if r > 0.1 and r < self.OBSTACLE_THRESHOLD:  # Valid reading and too close
                        return True
            return False
        
        if action == "FORWARD":
            if check_range(front_start, front_end):
                return "Obstacle detected ahead!"
        elif action == "BACKWARD":
            if check_range(back_start, back_end) or check_range(back_start2, num_readings):
                return "Obstacle detected behind!"
        elif action == "LEFT":
            if check_range(left_start, left_end):
                return "Obstacle detected on the left!"
        elif action == "RIGHT":
            if check_range(right_start, right_end):
                return "Obstacle detected on the right!"
        
        return None  # Safe to move

    def on_odom(self, msg: Odometry):
        """Update speed from odometry."""
        vx = msg.twist.twist.linear.x
        vy = msg.twist.twist.linear.y
        self.current_speed = math.sqrt(vx**2 + vy**2)

    def publish_status(self):
        """Publish JSON status for mobile app."""
        status = {
            "speed": f"{self.current_speed:.2f} m/s",
            "location": self.current_location,
            "battery": "85%" # Mock battery for now
        }
        msg = String()
        msg.data = json.dumps(status)
        self.status_pub.publish(msg)

    def get_robot_stats(self):
        """Reads CSV and returns the last 5 deliveries in simple format."""
        if not os.path.exists(self.csv_path):
            return "No history available."
            
        try:
            df = pd.read_csv(csv_path)
            if df.empty:
                return "History is empty."
            
            # Get last 5 rows - simple format
            last_5 = df.tail(5)
            
            history_str = "DELIVERY HISTORY:\n"
            for idx, (_, row) in enumerate(last_5.iterrows(), 1):
                date = row.get('Date_Full', '?')
                loc = row.get('Target_Location', '?')
                duration = row.get('Trip_Duration_Min', 0)
                distance = row.get('Distance_Traveled_M', 0)
                history_str += f"{idx}. {date} to {loc}, {duration}min, {distance}m\n"
                
            return history_str
        except Exception as e:
            self.get_logger().error(f"Stats error: {e}")
            return "Error reading history."

    def on_request(self, msg: String):
        user_text = msg.data.strip()
        if not user_text:
            return
        
        self.get_logger().info(f'Received chat request: {user_text}')
        
        # CHECK FOR SNAPSHOT REQUEST
        snapshot_keywords = ['snapshot', 'image', 'photo', 'picture', 'camera', 'see', 'صورة', 'تري', 'شايف', 'كاميرا']
        is_snapshot = any(kw in user_text.lower() for kw in snapshot_keywords)
        
        if is_snapshot and ('what' in user_text.lower() or 'can' in user_text.lower() or 'ماذا' in user_text.lower() or 'وريني' in user_text.lower() or 'send' in user_text.lower()):
            if self.latest_image:
                try:
                    # CompressedImage data is already jpg/png bytes
                    # Encode to Base64 string for transport
                    b64_str = base64.b64encode(self.latest_image.data).decode('utf-8')
                    
                    # Create response with hidden image tag
                    response = f"[IMAGE:{b64_str}] Here is what I see right now!"
                    self.publish_response(response)
                    return
                except Exception as e:
                    self.get_logger().error(f"Snapshot error: {e}")
                    self.publish_response("Sorry, I failed to process the image.")
                    return
            else:
                self.publish_response("I cannot see anything yet (Camera inactive).")
                return
        
        # CHECK FOR ANALYTICS QUERIES FIRST (Manual Computation)
        # This must come BEFORE comparison to handle "كم عدد الطلبات" correctly
        analytics_response = self.handle_analytics_query(user_text)
        if analytics_response:
            self.publish_response(analytics_response)
            return
        
        # CHECK FOR COMPARISON REQUEST (Manual Table Generation)
        # More specific: require "مقارن/قارن/آخر" + number pattern, not just "طلبات"
        comparison_keywords = ['مقارن', 'قارن', 'compare', 'comparison', 'آخر']
        has_number = any(c.isdigit() for c in user_text)
        is_comparison = any(kw in user_text.lower() for kw in comparison_keywords) or \
                        (has_number and ('طلبات' in user_text or 'orders' in user_text.lower() or 'trips' in user_text.lower()))
        
        if is_comparison:
            table_response = self.generate_comparison_table(user_text)
            if table_response:
                self.publish_response(table_response)
                return
        
        # CHECK FOR JOKE CRITICISM (Playful response)
        criticism_keywords = ['دمك تقيل', 'مش مضحك', 'خلاص نكت', 'متقولش نكت', 'كفايه نكت', 'بطل نكت', 'not funny', 'stop joking']
        is_criticism = any(kw in user_text for kw in criticism_keywords)
        
        if is_criticism:
            import random
            playful_responses = [
                "😅 ماشي ماشي... هسكت بس متزعلش مني! أنا روبوت حساس 🥺",
                "🙈 طيب خلاص مش هقول نكت تاني... إلا لو طلبت! 😜",
                "😢 حاضر... بس كدا جرحت مشاعري الإلكترونية! 💔🤖",
                "🤐 تمام، هركز في الشغل بس... بس كنت بحاول أفرحك! 😊",
                "😂 أوكي أوكي، أنا عارف إن نكتي محتاجة تحديث! Version 2.0 قريباً! 🔄",
            ]
            self.publish_response(random.choice(playful_responses))
            return
        
        # CHECK FOR JOKE REQUEST (Built-in jokes - bypass AI)
        joke_keywords = ['نكت', 'نكته', 'joke', 'funny', 'ضحك', 'هزار']
        is_joke = any(kw in user_text.lower() for kw in joke_keywords)
        
        if is_joke:
            joke_response = self.get_random_joke()
            self.publish_response(joke_response)
            return
        
        # CHECK FOR SELF-INTRODUCTION REQUEST
        intro_keywords = ['عرف', 'نفسك', 'من أنت', 'من انت', 'مين انت', 'who are you', 'introduce', 'yourself', 'about you', 'ما هو', 'ماهو']
        is_intro = any(kw in user_text.lower() for kw in intro_keywords)
        
        if is_intro:
            intro_response = self.get_self_introduction()
            self.publish_response(intro_response)
            return

        # DIRECT NAVIGATION COMMAND (Bypass AI for reliability)
        if self.handle_direct_navigation(user_text):
            return
        
        # Skip busy check - let Llama handle queuing
        if self._is_generating:
            self.get_logger().warn('Previous request still processing, will queue this one')
        
        if LLAMA_AVAILABLE and self.llama_client:
            self.send_to_llama(user_text)
        else:
            self.publish_response(f'Echo: {user_text}')

    def get_self_introduction(self):
        """Return detailed self-introduction for Rafiq."""
        intro = (
            "🤖 Hello! I am Rafiq (رفيق), your smart delivery robot assistant!\n\n"
            "📍 About Me:\n"
            "I was created by a team of Mechatronics Engineers from the Higher Technological Institute (HTI) "
            "in 10th of Ramadan City, Egypt. I was born in January 2026 as a graduation project.\n\n"
            "⚡ My Features:\n"
            "• Autonomous Navigation: I can navigate to any location on the map\n"
            "• QR Verification: I verify deliveries using QR codes\n"
            "• Vision System: I can see and detect gestures (thumbs up!)\n"
            "• Voice Interaction: I can speak and understand commands\n"
            "• Smart Analytics: I can analyze delivery history and statistics\n"
            "• Dual Language: I understand both Arabic and English\n\n"
            "I'm here to make deliveries faster and smarter! How can I help you today? 😊"
        )
        return intro

    def get_random_joke(self):
        """Return a random joke in Arabic."""
        import random
        jokes = [
            "😂 ليه الروبوت راح للدكتور؟ عشان عنده فيروس! 🤖💊",
            "😂 واحد روبوت قال للتاني: أنا حاسس إني متبرمج على الحزن! 😢",
            "😂 ليه الكمبيوتر راح للطبيب؟ عشان عنده بايت! 🖥️",
            "😂 أنا روبوت توصيل، لو اتأخرت عليك... اعتبرني بشر! 🚗",
            "😂 قالوا للروبوت: بتحلم بإيه؟ قال: بكهربا مستقرة! ⚡",
            "😂 ليه الروبوت مبيزعلش؟ عشان معندوش مشاعر... بس أنا مختلف! 💚",
            "😂 واحد سأل الـ GPS: أنت فين؟ قاله: أنا هنا... بس أنت فين؟! 📍",
            "😂 أنا رفيق، روبوت ذكي... بس لو ضحكت عليا هعمل نفسي مش فاهم! 🤖😜",
        ]
        return random.choice(jokes)

    def generate_comparison_table(self, user_text: str):
        """Generate a formatted comparison table from CSV data."""
        if not os.path.exists(self.csv_path):
            return None
            
        try:
            df = pd.read_csv(self.csv_path)
            if df.empty:
                return "لا توجد بيانات للمقارنة. ||| No data available for comparison."
            
            # Extract number from request (default 4)
            import re
            numbers = re.findall(r'\d+', user_text)
            requested_count = int(numbers[0]) if numbers else 4
            
            # Check available records
            available_count = len(df)
            
            # Apply limits: can't exceed available OR max display limit
            MAX_TABLE_ROWS = 10  # Prevent table from being too long
            actual_count = min(requested_count, available_count, MAX_TABLE_ROWS)
            
            # Track which limit was hit
            exceeded_available = requested_count > available_count
            exceeded_max = requested_count > MAX_TABLE_ROWS and available_count > MAX_TABLE_ROWS
            
            last_n = df.tail(actual_count)
            
            # Build Simple List Format (Mobile Friendly)
            table = f"📊 آخر {actual_count} طلبات (Last {actual_count} Orders):\n\n"
            
            for idx, (_, row) in enumerate(last_n.iterrows(), 1):
                date = str(row.get('Date_Full', '?'))[:10]
                loc = str(row.get('Target_Location', '?'))
                duration = row.get('Trip_Duration_Min', 0)
                distance = row.get('Distance_Traveled_M', 0)
                
                table += f"{idx}. {date}\n"
                table += f"   📍 {loc}\n"
                table += f"   ⏱️ {duration:.1f} دقيقة | 📏 {distance:.1f} متر\n\n"
            
            # Add note if any limit was exceeded
            if exceeded_max:
                table += f"⚠️ Max limit: {MAX_TABLE_ROWS}\n"
            elif exceeded_available:
                table += f"⚠️ Only {available_count} available.\n"
            
            # Mark as NO_VOICE to skip TTS
            table = "[NO_VOICE]" + table
            
            self.get_logger().info(f"Generated comparison table for {actual_count} orders")
            return table
            
        except Exception as e:
            self.get_logger().error(f"Table generation error: {e}")
            return None

    def handle_analytics_query(self, user_text: str):
        """Handle analytical queries like longest/shortest/average trip."""
        text_lower = user_text.lower()
        
        # Keywords for different analytics
        longest_kw = ['أطول', 'longest', 'اطول', 'الأطول']
        shortest_kw = ['أقصر', 'shortest', 'اقصر', 'الأقصر', 'fastest', 'اسرع', 'أسرع']
        average_kw = ['متوسط', 'average', 'mean', 'المتوسط']
        total_kw = ['إجمالي', 'total', 'كم', 'عدد', 'how many', 'count']
        
        # Check which type of query
        is_longest = any(kw in text_lower for kw in longest_kw)
        is_shortest = any(kw in text_lower for kw in shortest_kw)
        is_average = any(kw in text_lower for kw in average_kw)
        is_total = any(kw in text_lower for kw in total_kw)
        
        if not (is_longest or is_shortest or is_average or is_total):
            return None
        
        # Load CSV
        if not os.path.exists(self.csv_path):
            return "No delivery history available."
            
        try:
            df = pd.read_csv(self.csv_path)
            if df.empty:
                return "No deliveries recorded yet."
            
            # Determine if asking about duration or distance
            about_distance = any(kw in text_lower for kw in ['مسافة', 'distance', 'بعد', 'أبعد', 'ابعد'])
            
            if is_longest:
                if about_distance:
                    idx = df['Distance_Traveled_M'].idxmax()
                    row = df.loc[idx]
                    return f"📏 Longest Distance: {row['Distance_Traveled_M']:.1f}m to {row['Target_Location']} on {row['Date_Full']}"
                else:
                    idx = df['Trip_Duration_Min'].idxmax()
                    row = df.loc[idx]
                    return f"⏱️ Longest Trip: {row['Trip_Duration_Min']:.1f} min to {row['Target_Location']} on {row['Date_Full']}"
            
            elif is_shortest:
                if about_distance:
                    idx = df['Distance_Traveled_M'].idxmin()
                    row = df.loc[idx]
                    return f"📏 Shortest Distance: {row['Distance_Traveled_M']:.1f}m to {row['Target_Location']} on {row['Date_Full']}"
                else:
                    idx = df['Trip_Duration_Min'].idxmin()
                    row = df.loc[idx]
                    return f"⚡ Fastest Trip: {row['Trip_Duration_Min']:.1f} min to {row['Target_Location']} on {row['Date_Full']}"
            
            elif is_average:
                avg_duration = df['Trip_Duration_Min'].mean()
                avg_distance = df['Distance_Traveled_M'].mean()
                return f"📊 Averages:\n- Duration: {avg_duration:.1f} min\n- Distance: {avg_distance:.1f} m"
            
            elif is_total:
                total = len(df)
                return f"📦 Total Deliveries: {total} orders completed."
                
        except Exception as e:
            self.get_logger().error(f"Analytics error: {e}")
            return None
        
        return None

    def handle_direct_navigation(self, user_text: str):
        """Handle 'Go to X' commands directly without AI."""
        # Simple regex for finding location
        import re
        match = re.search(r"(?:go to|drive to|navigate to|move to|روح|اذهب الى|اذهب ل) (.+)", user_text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Clean up punctuation
            location = location.rstrip('.!?')
            
            self.get_logger().info(f"🚀 Direct Navigation Triggered: {location}")
            self.current_location = f"Going to {location}"
            
            # 1. Publish to direct_nav (NO order creation)
            msg = String()
            msg.data = location
            self.direct_nav_pub.publish(msg)
            
            # 2. Respond
            self.publish_response(f"🚀 Heading to {location}")
            return True
        return False

    def send_to_llama(self, prompt: str):
        if not self.llama_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().warn('Llama action server not available')
            self.publish_response('Sorry, AI is not available right now.')
            return
        
        # Reset accumulator
        self._accumulated_response = ""
        self._is_generating = True
        
        goal = GenerateResponse.Goal()
        
        # CONTEXT
        stats_context = self.get_robot_stats()
        vision_context = f"LIVE VISION: I currently see: {self.latest_vision}"
        
        now = datetime.datetime.now()
        time_context = f"CURRENT DATETIME: {now.strftime('%A, %Y-%m-%d %H:%M:%S')}"
        
        system_instr = (
            "You are Rafiq (رفيق), a smart delivery robot assistant. "
            "1. NAVIGATION: Only if user asks to go to a specific place, output [COMMAND: LocationName]. "
            "   Example: 'Go to Kitchen' -> '[COMMAND: Kitchen] Going to Kitchen.' "
            "2. MOTION: [ACTION: FORWARD], [ACTION: BACKWARD], [ACTION: LEFT], [ACTION: RIGHT], [ACTION: STOP]. "
            "3. INFO: Use the DELIVERY HISTORY table below to answer questions about past deliveries. "
            "4. COMPARISON: When user asks to compare trips, summarize the table data (Location, Duration, Distance). "
            "5. VISION: I will provide LIVE VISION data. Use it to answer 'What do you see?'. "
            "6. OUTPUT FORMAT: Check the user's language. "
            "   - IF USER SPEAKS ENGLISH: Reply in English. DO NOT use '|||'. "
            "   - IF USER SPEAKS ARABIC: Reply in Arabic, then YOU MUST append '|||' followed by the English translation. "
            "     Example: 'مرحباً ||| Hello there.'"
        )
        
        # ChatML Format
        full_prompt = (
            f"<|im_start|>system\n{system_instr}\n\n"
            f"{time_context}\n\n"
            f"{stats_context}\n\n"
            f"{vision_context}\n<|im_end|>\n"
            f"<|im_start|>user\n{prompt}\n<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        
        self.get_logger().info(f"PROMPT: {full_prompt}")
        
        goal.prompt = full_prompt
        goal.reset = True
        
        future = self.llama_client.send_goal_async(goal, feedback_callback=self.on_llama_feedback)
        future.add_done_callback(self.on_llama_goal_response)

    def on_llama_feedback(self, feedback_msg):
        try:
            partial = feedback_msg.feedback.partial_response
            token_text = partial.text if hasattr(partial, 'text') else ""
            if token_text:
                self._accumulated_response += token_text
        except Exception as e:
            self.get_logger().error(f'Feedback error: {e}')

    def on_llama_goal_response(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('Goal rejected (AI busy)')
            self._is_generating = False
            return
        
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.on_llama_result)

    def on_llama_result(self, future):
        self._is_generating = False
        response_text = ""
        
        try:
            result = future.result().result
            if hasattr(result, 'response') and hasattr(result.response, 'text') and result.response.text:
                response_text = result.response.text
            elif hasattr(result, 'text') and result.text:
                response_text = result.text
        except Exception as e:
            self.get_logger().error(f'Result extraction error: {e}')

        if not response_text:
            response_text = self._accumulated_response.strip()
        
        if not response_text:
            response_text = "ERROR: Empty response from AI."
        
        self.get_logger().info(f'Final Llama response: {response_text[:100]}...')
        
        self.execute_command(response_text)
        
        # Clean Tags
        clean_text = response_text.replace("[COMMAND:", "").replace("[ACTION:", "").replace("]", "")
        clean_text = clean_text.replace("<|im_end|>", "").replace("<|im_start|>", "").strip()
        
        # Split for Dual Language (Chat vs Voice)
        chat_text = clean_text
        voice_text = clean_text
        
        if "|||" in clean_text:
            parts = clean_text.split("|||")
            chat_text = parts[0].strip()
            voice_text = parts[1].strip()
            
        # FORCE PROPER ENGLISH VOICE: Remove non-ascii characters from voice_text
        # This removes Arabic leaks, keeping only English, numbers, and punctuation.
        voice_text = re.sub(r'[^\x00-\x7F]+', '', voice_text).strip()
        
        self.get_logger().info(f"Dual Lang: Chat='{chat_text[:30]}...', Voice='{voice_text[:30]}...'")
        self.publish_response(chat_text, voice_text)

    def publish_response(self, chat_text: str, voice_text: str = None):
        # Check for NO_VOICE marker (skip TTS for tables, etc.)
        skip_voice = chat_text.startswith("[NO_VOICE]")
        if skip_voice:
            chat_text = chat_text.replace("[NO_VOICE]", "")
        
        if voice_text is None:
            voice_text = chat_text
            
        # Create JSON Payload
        payload = {
            "text": chat_text,
            "voice": voice_text if not skip_voice else ""
        }
        
        try:
            json_str = json.dumps(payload)
            msg = String()
            msg.data = json_str
            self.response_pub.publish(msg)
            self.get_logger().info(f'Published chat JSON: {json_str[:100]}...')
        except Exception as e:
            self.get_logger().error(f"Failed to publish JSON response: {e}")

        # 2. Voice Response - DISABLED for chat (mobile app handles TTS)
        # TTS is only used in qr_scanner.py for delivery announcements
        # if self.tts_client and not skip_voice:
        #     self.speak(voice_text)

    def on_map_markers(self, msg: MarkerArray):
        """Receive markers from goal_name.py and forward to mobile app."""
        waypoints_data = []
        try:
            for marker in msg.markers:
                # We only care about Text markers for the names (Type 9)
                if marker.type == 9:
                    waypoints_data.append({
                        "name": marker.text,
                        "x": marker.pose.position.x,
                        "y": marker.pose.position.y
                    })
            
            if waypoints_data:
                json_msg = String()
                json_msg.data = json.dumps(waypoints_data)
                self.waypoints_pub.publish(json_msg)
                
                # Update Cache
                self.cached_waypoints_msg = json_msg
                
        except Exception as e:
            self.get_logger().error(f"Error bridging markers: {e}")

        # Log success for debugging
        if waypoints_data:
            count = len(waypoints_data)
            self.get_logger().info(f"Bridged {count} waypoints to app.")
            # Debug: Show on UI Status Chip
            self.current_location = f"Markers Loaded: {count}"

    def publish_cached_waypoints(self):
        """Periodically republish waypoints to ensure UI persistence on reconnect."""
        if self.cached_waypoints_msg:
            self.waypoints_pub.publish(self.cached_waypoints_msg)

    def speak(self, text: str):
        if not self.tts_client.wait_for_server(timeout_sec=2.0):
            # Don't block too long for voice
            self.get_logger().warn("TTS server taking too long, skipping voice")
            return
            
        goal = TTS.Goal()
        goal.text = text
        self.tts_client.send_goal_async(goal)

def main(args=None):
    rclpy.init(args=args)
    node = ChatBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

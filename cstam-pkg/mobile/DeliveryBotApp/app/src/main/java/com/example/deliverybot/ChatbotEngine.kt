package com.example.deliverybot

/**
 * Intelligent Chatbot Engine for Autonomous Delivery Robot
 * HTI Mechatronics Engineering Graduation Project
 *
 * This engine provides offline, rule-based responses about:
 * - Robot capabilities and features
 * - App usage instructions
 * - Team and project information
 * - Technical details about ROS 2 implementation
 */
class ChatbotEngine {

    // Response categories for intelligent matching
    private data class BotResponse(
        val keywords: List<String>,
        val response: String,
        val priority: Int = 1
    )

    private val responses = listOf(
        // Chatbot Architecture
        BotResponse(
            keywords = listOf("chatbot", "llama", "ai model", "talk", "voice", "architect", "consist", "how do you work", "components", "inside"),
            response = "🧠 **Advanced Chatbot Architecture:**\n\n" +
                    "My intelligence is powered by a sophisticated ROS 2 pipeline running locally on the robot:\n\n" +
                    "👂 **Hearing (Speech-to-Text):**\n" +
                    "• **`whisper_ros`**: Uses OpenAI's **Whisper** model to convert your voice into text with high accuracy.\n" +
                    "• **`audio_common`**: Handles raw audio capture and processing.\n\n" +
                    "🧠 **Thinking (Generative AI):**\n" +
                    "• **`llama_ros`**: Runs **Llama 3.2**, a powerful Large Language Model (LLM), to understand context and generate intelligent answers.\n" +
                    "• **`chatbot_ros`**: The core node managing conversation flow.\n\n" +
                    "🗣️ **Speaking (Text-to-Speech):**\n" +
                    "• **`piper_ros`**: Uses **Piper**, a fast neural TTS system, to speak back to you naturally.\n\n" +
                    "⚙️ **Orchestration:**\n" +
                    "• **`yasmin`**: (Yet Another State MachINe) manages complex robot behaviors and states.\n" +
                    "• **ROSBridge**: Connects this Android app to the robot via WebSocket.\n\n" +
                    "I am a fully offline, privacy-focused AI running on the Edge! 🚀",
            priority = 3
        ),

        // Gesture Recognition (YOLO)
        BotResponse(
            keywords = listOf("gesture", "yolo", "ai", "like", "thumbs up", "recognition", "sign"),
            response = "👍 **Gesture Recognition AI:**\n\n" +
                    "I use a YOLOv6 AI model to see and understand you!\n\n" +
                    "**How it works:**\n" +
                    "1. When I arrive with your delivery...\n" +
                    "2. Show me a **'Thumbs Up' (Like)** gesture 👍\n" +
                    "3. I will detect it instantly!\n" +
                    "4. This confirms you received the order\n" +
                    "5. I'll automatically return to home base\n\n" +
                    "No need to touch the screen, just give me a Like! ✨",
            priority = 3
        ),

        // QR Verification
        BotResponse(
            keywords = listOf("qr", "code", "scan", "verification", "security", "verify"),
            response = "🔐 **Secure QR Verification:**\n\n" +
                    "I ensure packages go to the right person!\n\n" +
                    "**The Process:**\n" +
                    "1. When I arrive, I show a camera preview\n" +
                    "2. Show your unique **Order QR Code** from the app\n" +
                    "3. I scan and verify it securely\n" +
                    "4. If valid, the locker unlocks!\n\n" +
                    "Safety and security first! 🛡️",
            priority = 3
        ),

        // Obstacle Avoidance
        BotResponse(
            keywords = listOf("obstacle", "avoid", "collision", "safety", "lidar", "sensor"),
            response = "🚧 **Obstacle Avoidance System:**\n\n" +
                    "I navigate safely around people and objects!\n\n" +
                    "**Sensors:**\n" +
                    "• **Lidar:** 360-degree laser scanning\n" +
                    "• **Ultrasonic:** Close-range detection\n\n" +
                    "**Behavior:**\n" +
                    "• I stop for dynamic obstacles (people)\n" +
                    "• I planned paths around static objects\n" +
                    "• I constantly update my local costmap\n\n" +
                    "We can share the hallway safely! 🤝",
            priority = 3
        ),
        // Greetings and Introduction
        BotResponse(
            keywords = listOf("hello", "hi", "hey", "greetings", "good morning", "good evening"),
            response = "Hello! 👋 I'm your Autonomous Delivery Robot assistant. I'm here to help you with:\n\n" +
                    "📱 App features and usage\n" +
                    "🤖 Robot capabilities\n" +
                    "🗺️ Navigation and mapping\n" +
                    "📦 Order management\n" +
                    "⚙️ Technical information\n\n" +
                    "What would you like to know?",
            priority = 2
        ),

        // About the Project and Team
        BotResponse(
            keywords = listOf("project", "graduation", "team", "hti", "about", "creators", "made", "who are you"),
            response = "🎓 **HTI Mechatronics Graduation Project**\n\n" +
                    "Developed by Mechatronics Engineering students:\n\n" +
                    "💻 **Software Team:**\n" +
                    "• Mohammed Nasser Abdelhady\n" +
                    "• Abdulrahman Muhammad Muhammad\n" +
                    "• Jack Isaac Boshra\n" +
                    "• Reem Sayed Saad\n\n" +
                    "⚙️ **Mechanical Team:**\n" +
                    "• Kareem Ahmed Taha\n" +
                    "• Seif Ayman Hassan\n" +
                    "• Eslam Tohamy Shaaban\n\n" +
                    "👨‍🏫 **Supervisors:**\n" +
                    "• Prof. Dr. Amal Ibrahim\n" +
                    "• Dr. Ahmed El-Sayed\n\n" +
                    "Powered by ROS 2 Humble & Android!",
            priority = 2
        ),

        // About the Robot
        BotResponse(
            keywords = listOf("robot", "autonomous", "delivery", "capabilities", "what can", "specs", "hardware"),
            response = "🤖 **Autonomous Delivery Robot Specs:**\n\n" +
                    "Built on the **Andino** open-source platform:\n\n" +
                    "🧠 **Brain:** Raspberry Pi 4 (ROS 2 Humble)\n" +
                    "👁️ **Vision:** Raspberry Pi Camera V2\n" +
                    "📡 **Sensors:**\n" +
                    "• **RPLIDAR A1:** 360° Laser Scanning for SLAM\n" +
                    "• **Ultrasonic:** Short-range obstacle detection\n" +
                    "• **Odometry:** Wheel encoders for position tracking\n\n" +
                    "⚡ **Actuation:**\n" +
                    "• Differential Drive System\n" +
                    "• High-torque DC Motors with encoders\n\n" +
                    "A robust mechatronics system designed for indoor logistics! 🏭",
            priority = 3
        ),

        // App Features Overview
        BotResponse(
            keywords = listOf("app", "features", "application", "android", "tech stack"),
            response = "📱 **Mobile App Architecture:**\n\n" +
                    "A Native Android application built with **Kotlin**:\n\n" +
                    "� **Connectivity:**\n" +
                    "• Uses **ROSBridgeClient** (WebSocket) to talk to ROS 2.\n" +
                    "• Port: 9090 (JSON commands)\n\n" +
                    "�️ **UI/UX:**\n" +
                    "• **WebView:** For Map & Camera visualization.\n" +
                    "• **RecyclerView:** For Chat & Logs.\n" +
                    "• **Neon Theme:** Custom XML drawables.\n\n" +
                    "🧠 **AI Integration:**\n" +
                    "• **Text-to-Speech (TTS):** Native Android API.\n" +
                    "• **Speech Recognition:** Android Intent API.\n\n" +
                    "The perfect interface for human-robot interaction! 🤝",
            priority = 2
        ),

        // Map and Navigation
        BotResponse(
            keywords = listOf("map", "mapping", "slam", "navigate", "navigation", "costmap", "planner"),
            response = "🗺️ **Navigation Stack (Nav2):**\n\n" +
                    "We use the industry-standard **ROS 2 Navigation Stack**:\n\n" +
                    "📍 **Mapping (SLAM):**\n" +
                    "• **Pkg:** `slam_toolbox`\n" +
                    "• **Algo:** Graph-based SLAM\n" +
                    "• Builds map from Lidar scans + Odometry\n\n" +
                    "🧭 **Localization:**\n" +
                    "• **Pkg:** `nav2_amcl`\n" +
                    "• Uses particle filter to find position\n\n" +
                    "�️ **Path Planning:**\n" +
                    "• **Global:** A* / Dijkstra (finds best route)\n" +
                    "• **Local:** DWB Controller (avoids dynamic obstacles)\n" +
                    "• **Costmaps:** Layers for static/dynamic obstacles\n\n" +
                    "State-of-the-art autonomous movement! 🚀",
            priority = 3
        ),

        // Camera Feature
        BotResponse(
            keywords = listOf("camera", "video", "stream", "mjpeg", "view", "watch"),
            response = "📹 **Video Streaming Pipeline:**\n\n" +
                    "Low-latency streaming for real-time monitoring:\n\n" +
                    "1. **Capture:** `v4l2_camera` node reads raw frames.\n" +
                    "2. **Compression:** Converted to JPEG to save bandwidth.\n" +
                    "3. **Server:** `web_video_server` ROS node.\n" +
                    "4. **Protocol:** HTTP MJPEG Stream.\n" +
                    "5. **Display:** Android WebView renders the stream URL.\n\n" +
                    "Optimized for speed and minimal lag! ⚡",
            priority = 2
        ),

        // Teleop Control
        BotResponse(
            keywords = listOf("control", "teleop", "drive", "twist", "cmd_vel", "manual"),
            response = "🎮 **Control Logic:**\n\n" +
                    "Manual control bypasses the autonomous planner:\n\n" +
                    "1. **Input:** You press buttons on the App.\n" +
                    "2. **Publish:** App sends JSON to `/cmd_vel` topic.\n" +
                    "3. **Message Type:** `geometry_msgs/Twist`\n" +
                    "   • `linear.x` (Speed)\n" +
                    "   • `angular.z` (Turn)\n" +
                    "4. **Hardware:** Microcontroller receives Twist -> PWM -> Motors.\n\n" +
                    "Direct control at your fingertips! 🕹️",
            priority = 2
        ),

        // Orders and Delivery
        BotResponse(
            keywords = listOf("order", "delivery", "mission", "goal", "waypoint"),
            response = "📦 **Delivery Mission Logic:**\n\n" +
                    "How a delivery executes technically:\n\n" +
                    "1. **Goal:** You select 'Cafeteria' (Coordinates x,y,yaw).\n" +
                    "2. **Action:** App sends `NavigateToPose` action goal.\n" +
                    "3. **Plan:** Nav2 computes global path.\n" +
                    "4. **Execution:** Robot follows path using local controller.\n" +
                    "5. **Arrival:** Robot enters 'Waiting' state for QR/Gesture.\n\n" +
                    "Fully autonomous state-machine behavior! 🤖",
            priority = 2
        ),

        // Connection and Setup
        BotResponse(
            keywords = listOf("connect", "rosbridge", "websocket", "network", "ip"),
            response = "🔌 **Communication Bridge:**\n\n" +
                    "The detailed link between Android and ROS 2:\n\n" +
                    "• **Package:** `rosbridge_suite`\n" +
                    "• **Protocol:** WebSocket (TCP)\n" +
                    "• **Format:** JSON Serialization\n" +
                    "• **Topics:**\n" +
                    "   - Subscribes to: `/cmd_vel`, `/move_base_simple/goal`\n" +
                    "   - Publishes to: `/app/chat/status`, `/odom`\n\n" +
                    "Reliable, real-time, bidirectional data link! 🌐",
            priority = 3
        ),

        // Dashboard and Analytics
        BotResponse(
            keywords = listOf("dashboard", "analytics", "stats", "statistics", "report", "pdf", "csv", "data", "dataframe"),
            response = "📊 **Smart Dashboard & Analytics:**\n\n" +
                    "A powerful **Streamlit** dashboard for data-driven insights:\n\n" +
                    "🔄 **Live Updates:**\n" +
                    "• The DataFrame updates automatically with every new order.\n" +
                    "• Real-time visualization of mission success rates.\n\n" +
                    "📉 **Advanced Analytics:**\n" +
                    "• Filter data by Date, Location, or Status.\n" +
                    "• View delivery trends and performance metrics.\n\n" +
                    "📥 **Export Reports:**\n" +
                    "• **PDF Reports:** Download professional mission summaries.\n" +
                    "• **CSV Data:** Export raw datasets for external analysis.\n" +
                    "• Select any custom time range for specific reports.\n\n" +
                    "Turning raw robot data into actionable intelligence! 🧠",
            priority = 3
        ),

        // Settings (Simple UI, no complex tech)
        BotResponse(
            keywords = listOf("settings", "preferences", "config"),
            response = "⚙️ **App Configuration:**\n\n" +
                    "• **Shared Preferences:** Stores your robot IP and dark mode setting locally on the phone.\n" +
                    "• **Dynamic UI:** Layouts update instantly without app restart.\n\n" +
                    "Simple and persistent! 💾",
            priority = 2
        ),

        // Connection and Setup
        BotResponse(
            keywords = listOf("simulation", "gazebo", "sim", "virtual"),
            response = "🖥️ **Simulation Environment:**\n\n" +
                    "Used for testing without hardware:\n\n" +
                    "• **Simulator:** Gazebo Fortress / Ignition\n" +
                    "• **Package:** `andino_gz`\n" +
                    "• **World:** Custom 'Office' world (.sdf)\n" +
                    "• **Physics:** Real-time physics engine for collisions and gravity.\n\n" +
                    "Digital twin technology for safe validation! 🧪",
            priority = 2
        ),


        // How to Use App
        BotResponse(
            keywords = listOf("how to use", "tutorial", "guide", "help", "start", "begin"),
            response = "📚 **Getting Started Guide:**\n\n" +
                    "**Step 1: Connection**\n" +
                    "• Ensure robot is powered on\n" +
                    "• Connect to same network\n" +
                    "• App auto-connects via ROSBridge\n\n" +
                    "**Step 2: Monitor**\n" +
                    "• View map in 'Map Viewer'\n" +
                    "• Check camera feed\n" +
                    "• Monitor robot status\n\n" +
                    "**Step 3: Control**\n" +
                    "• Create delivery orders OR\n" +
                    "• Use manual teleop control\n\n" +
                    "**Step 4: Track**\n" +
                    "• Monitor delivery progress\n" +
                    "• View order history\n\n" +
                    "Need help with a specific feature? Just ask!",
            priority = 2
        ),

        // Troubleshooting
        BotResponse(
            keywords = listOf("problem", "issue", "error", "not working", "fix", "troubleshoot", "help"),
            response = "🔧 **Troubleshooting:**\n\n" +
                    "**Common Issues:**\n\n" +
                    "❌ **Can't Connect:**\n" +
                    "• Check robot is powered on\n" +
                    "• Verify same WiFi network\n" +
                    "• Restart ROSBridge server\n" +
                    "• Check IP address in settings\n\n" +
                    "❌ **No Map Display:**\n" +
                    "• Ensure SLAM is running\n" +
                    "• Check map topic is published\n" +
                    "• Verify connection status\n\n" +
                    "❌ **Camera Not Working:**\n" +
                    "• Check camera is connected\n" +
                    "• Verify video topic\n" +
                    "• Restart camera node\n\n" +
                    "Still having issues? Check robot logs!",
            priority = 2
        ),

        // Thanks and Goodbye
        BotResponse(
            keywords = listOf("thank", "thanks", "appreciate", "helpful"),
            response = "You're welcome! 😊 I'm happy to help!\n\n" +
                    "Feel free to ask me anything about:\n" +
                    "• Using the app\n" +
                    "• Robot features\n" +
                    "• Technical details\n" +
                    "• Project information\n\n" +
                    "Good luck with your delivery! 🚀",
            priority = 1
        ),

        BotResponse(
            keywords = listOf("bye", "goodbye", "see you", "exit", "quit"),
            response = "Goodbye! 👋 Come back anytime you need help!\n\n" +
                    "Have a great day with your Autonomous Delivery Robot! 🤖📦",
            priority = 1
        ),

        // Default/Fallback Response
        BotResponse(
            keywords = listOf(""),
            response = "I'm here to help! 🤖\n\n" +
                    "I can answer questions about:\n\n" +
                    "🗺️ Mapping and navigation\n" +
                    "📹 Camera streaming\n" +
                    "🎮 Robot control\n" +
                    "📦 Order management\n" +
                    "⚙️ Technical details\n" +
                    "🎓 Project information\n\n" +
                    "What would you like to know?",
            priority = 0
        )
    )

    /**
     * Get welcome message shown when chat starts
     */
    fun getWelcomeMessage(): String {
        return "👋 **Welcome to Autonomous Delivery Robot Assistant!**\n\n" +
                "🎓 **HTI Mechatronics Graduation Project**\n\n" +
                "I'm your intelligent assistant for the Autonomous Mobile Delivery Robot. " +
                "I can help you with everything related to our robot and this app!\n\n" +
                "🤖 **About Our Robot:**\n" +
                "• Autonomous navigation\n" +
                "• Real-time SLAM mapping\n" +
                "• Live camera streaming\n" +
                "• Package delivery system\n\n" +
                "💬 **Ask Me About:**\n" +
                "• How to use app features\n" +
                "• Robot capabilities\n" +
                "• Navigation & mapping\n" +
                "• Creating orders\n" +
                "• Technical details\n\n" +
                "Feel free to ask me anything! 😊"
    }

    /**
     * Get intelligent response based on user message
     * Uses keyword matching with priority scoring
     */
    fun getResponse(userMessage: String): String {
        val message = userMessage.lowercase().trim()

        // Empty message handling
        if (message.isEmpty()) {
            return "Please type a message! I'm here to help. 😊"
        }

        // Find best matching response
        var bestMatch: BotResponse? = null
        var highestScore = 0

        for (response in responses) {
            var score = 0

            // Calculate match score based on keywords
            for (keyword in response.keywords) {
                if (message.contains(keyword)) {
                    score += response.priority
                }
            }

            // Update best match if this score is higher
            if (score > highestScore) {
                highestScore = score
                bestMatch = response
            }
        }

        // Return best match or default response
        return bestMatch?.response ?: responses.last().response
    }

    /**
     * Get suggested questions user might ask
     */
    fun getSuggestedQuestions(): List<String> {
        return listOf(
            "What can this robot do?",
            "How do I create an order?",
            "Show me app features",
            "How does navigation work?",
            "Tell me about the project",
            "How to use teleop control?",
            "What is SLAM?",
            "Camera not working"
        )
    }
}
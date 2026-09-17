# Chatbot System Requirements & Setup

This document outlines the dependencies and setup required to run the Delivery Bot's Advanced Chatbot features (Vision, Voice, and AI).

## 1. Core ROS 2 Dependencies

The chatbot integration relies on the **Advanced Integration** packages maintained by `mgonzs13`. You must have these packages in your workspace or installed on your system.

### Option A: Install via Source (Recommended)
If these packages are not present, clone them into your workspace `src` folder:

```bash
cd ~/ws/src

# Llama (LLM) Integration
git clone https://github.com/mgonzs13/llama_ros.git

# Piper (TTS) Integration
git clone https://github.com/mgonzs13/piper_ros.git

# Whisper (STT) Integration (Optional)
git clone https://github.com/mgonzs13/whisper_ros.git

# Audio Common (Audio I/O)
git clone https://github.com/mgonzs13/audio_common.git
```

After cloning, ensure strict dependency installation:

```bash
cd ~/ws
rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

## 2. Python Dependencies

The `chat_bridge.py` script requires `pandas` to read and format the delivery history logs (CSV).

```bash
pip3 install pandas
```

*(Note: `rclpy` and other standard libraries are included with ROS 2).*

## 3. AI Models (Automatic Download)

The system is configured to **automatically download** the required AI models on the first launch. Please ensure you have an active internet connection when running the app for the first time.

### Models Used:
1.  **Large Language Model (LLM):**
    *   **Model:** `Qwen2.5-Coder-3B-Instruct-GGUF`
    *   **Size:** ~2.5 GB
    *   **Purpose:** Reasoning, Conversation, Translation (Ar/En).
    *   **Launch Download:** Automatically handled by `llama_bringup`.

2.  **Text-to-Speech (TTS):**
    *   **Voice:** `en_US-lessac-medium`
    *   **Size:** ~50 MB
    *   **Purpose:** English Voice Generation.
    *   **Launch Download:** Automatically handled by `piper_bringup`.

## 4. Troubleshooting

*   **Missing Models:** If the robot is silent or "Empty Response", check if the models failed to download. You can check the logs for download errors.
*   **Build Issues:** Ensure `audio_common` is built correctly as it handles the audio stream for Piper.
*   **Voice Language:** The robot is configured to speak **English Only**. Arabic text is translated automatically by the system before being sent to the voice engine.

# QR Verification Package

This ROS2 package provides nodes for generating and scanning QR codes to verify deliveries.

## Nodes

### 1. `qr_generator`

Generates QR codes when triggered.

- **Subscriptions**:
    - `/app/qr/generate` (std_msgs/String): Trigger generation. Expects JSON `{"order_id": "...", "address": "..."}`.
    - `/app/goal_name` (std_msgs/String): Tracks location to enable generation only when robot has left base.
- **Publications**:
    - `/app/qr/image` (std_msgs/String): Path to generated QR image.
- **Parameters**:
    - `mission_root`: Path to missions directory.
    - `order_history_path`: Path to order history log.

### 2. `qr_scanner`

Scans for QR codes using camera feed.

- **Subscriptions**:
    - `/app/order_created`: Triggers expectation of a specific Order ID.
    - `/robot/goal_status`: Triggers scanning when arrived.
    - `/camera/image_raw/compressed`: Camera feed.
- **Publications**:
    - `/robot/qr/scanned`: Payload of scanned QR.
    - `/robot/qr/verified`: Boolean result.
- **Parameters**:
    - `use_webcam` (bool): If True, uses laptop webcam (simulation mode).
    - `scan_timeout` (double): Seconds before timeout.
    - `audio_assets_path` (string): Path to audio files.

## Installed Libraries & Versions

The following libraries are used in this package:

- **opencv-python-headless** (cv2): Used for image processing and GUI. 
- **numpy**: Matrix operations for images.
- **qrcode**: Generating QR codes.
- **Pillow (PIL)**: Image manipulation.
- **pyzbar**: QR code decoding.
- **pygame**: Audio playback.

Ensure these are installed in your environment (e.g., via `pip` or `rosdep`).

## Installation

1.  Clone into `src/` of your workspace.
2.  Install dependencies:
    ```bash
    cd ~/ws
    rosdep install --from-paths src --ignore-src -r -y
    ```
3.  Build:
    ```bash
    colcon build --packages-select qr_verification --symlink-install
    ```

## Usage

Launch the system with:

```bash
ros2 launch qr_verification qr_system.launch.py
```

### Simulation Mode

To use laptop webcam:

```bash
ros2 launch qr_verification qr_system.launch.py use_webcam:=True
```

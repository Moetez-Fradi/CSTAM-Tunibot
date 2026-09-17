#!/bin/bash
echo "🤖 Delivery Bot Dependency Installer"
echo "===================================="

# 1. Update System
echo "[1/4] Updating Apt..."
sudo apt-get update
sudo apt-get install -y wget

# 2. Install ROS Dependencies (rosdep)
echo "[2/4] Installing ROS System Dependencies..."
if ! command -v rosdep &> /dev/null; then
    sudo apt-get install -y python3-rosdep
    sudo rosdep init
    rosdep update
fi

# Install dependencies for all packages in src
rosdep install --from-paths src --ignore-src -r -y

# 3. Install Python Dependencies
echo "[3/4] Installing Python Libraries..."
pip3 install -r requirements.txt

# 4. Optional: Yasmin Web Client Warning
echo "[4/4] Checking Yasmin Viewer..."
YASMIN_BUILD_DIR="src/App/chatbot/yasmin/yasmin_viewer/yasmin_viewer_web_client/build"
if [ ! -d "$YASMIN_BUILD_DIR" ]; then
    echo "⚠️  Yasmin Viewer Web Client missing (Expected)."
    echo "   The system will work, but if you want the visual editor, run:"
    echo "   cd src/App/chatbot/yasmin/yasmin_viewer/yasmin_viewer_web_client && npm install && npm run build"
else
    echo "✅ Yasmin Viewer Web Client found."
fi

# 5. Manual Dependencies (ONNX Runtime for Piper)
echo "[5/5] Installing ONNX Runtime (Required for Piper)..."
if [ ! -f "/usr/local/include/onnxruntime_cxx_api.h" ] && [ ! -f "/usr/include/onnxruntime_cxx_api.h" ]; then
    ARCH=$(uname -m)
    ONNX_VERSION="1.14.1"
    
    if [ "$ARCH" == "x86_64" ]; then
        ONNX_URL="https://github.com/microsoft/onnxruntime/releases/download/v${ONNX_VERSION}/onnxruntime-linux-x64-${ONNX_VERSION}.tgz"
        ONNX_DIR="onnxruntime-linux-x64-${ONNX_VERSION}"
    elif [ "$ARCH" == "aarch64" ]; then
        ONNX_URL="https://github.com/microsoft/onnxruntime/releases/download/v${ONNX_VERSION}/onnxruntime-linux-aarch64-${ONNX_VERSION}.tgz"
        ONNX_DIR="onnxruntime-linux-aarch64-${ONNX_VERSION}"
    else
        echo "⚠️  Unsupported architecture for auto-ONNX install: $ARCH"
        echo "   Please install onnxruntime manually if piper_vendor fails."
        ONNX_URL=""
    fi

    if [ ! -z "$ONNX_URL" ]; then
        echo "   Downloading ONNX Runtime v${ONNX_VERSION}..."
        wget -q --show-progress "$ONNX_URL" -O /tmp/onnxruntime.tgz
        
        echo "   Extracting..."
        tar -xzf /tmp/onnxruntime.tgz -C /tmp
        
        echo "   Installing to /usr/local..."
        # Copy headers
        sudo cp -r /tmp/${ONNX_DIR}/include/* /usr/local/include/
        # Copy libs
        sudo cp -r /tmp/${ONNX_DIR}/lib/* /usr/local/lib/
        
        sudo ldconfig
        
        # Cleanup
        rm /tmp/onnxruntime.tgz
        rm -rf /tmp/${ONNX_DIR}
        
        echo "✅ ONNX Runtime installed successfully."
    fi
else
    echo "✅ ONNX Runtime header found. Skipping install."
fi

echo "===================================="
echo "✅ Installation Complete! Please run 'colcon build' now."

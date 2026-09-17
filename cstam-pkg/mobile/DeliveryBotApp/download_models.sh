#!/bin/bash
set -e

ASSET_DIR="/home/mo/ws/mobile/DeliveryBotApp/app/src/main/assets/sherpa"
mkdir -p "$ASSET_DIR"
cd "$ASSET_DIR"

# ENGLISH MODELS
echo "Downloading English Female (Amy)..."
if [ ! -d "model-en-female" ]; then
    wget -q -O amy.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-amy-low.tar.bz2
    tar -xjf amy.tar.bz2
    mv vits-piper-en_US-amy-low model-en-female
    rm amy.tar.bz2
fi

echo "Downloading English Male (Ryan)..."
if [ ! -d "model-en-male" ]; then
    wget -q -O ryan.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-ryan-low.tar.bz2
    tar -xjf ryan.tar.bz2
    mv vits-piper-en_US-ryan-low model-en-male
    rm ryan.tar.bz2
fi

# ARABIC MODELS
echo "Downloading Arabic Male (Kareem - Piper)..."
if [ ! -d "model-ar-male" ]; then
    wget -q -O kareem.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-ar_JO-kareem-low.tar.bz2
    tar -xjf kareem.tar.bz2
    mv vits-piper-ar_JO-kareem-low model-ar-male
    rm kareem.tar.bz2
fi

echo "Downloading Arabic Female (Dana - Piper)..."
if [ ! -d "model-ar-female" ]; then
    wget -q -O dana.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-ar_JO-dana-low.tar.bz2
    tar -xjf dana.tar.bz2
    mv vits-piper-ar_JO-dana-low model-ar-female
    rm dana.tar.bz2
fi

echo "Downloading Egyptian Arabic (MMS)..."
if [ ! -d "model-ar-egypt" ]; then
    # MMS arz (Egyptian)
    wget -q -O arz.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-mms-arz-arz.tar.bz2
    tar -xjf arz.tar.bz2
    mv vits-mms-arz-arz model-ar-egypt
    rm arz.tar.bz2
fi

echo "All models downloaded to $ASSET_DIR"
ls -F

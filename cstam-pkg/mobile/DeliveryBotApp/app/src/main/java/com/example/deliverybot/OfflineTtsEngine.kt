package com.example.deliverybot

import android.content.Context
import android.speech.tts.TextToSpeech
import android.util.Log
import java.util.Locale

// Replaced Sherpa-ONNX with Native Android TTS for speed and reliability
object OfflineTtsEngine : TextToSpeech.OnInitListener {
    private const val TAG = "OfflineTtsEngine"
    
    private var tts: TextToSpeech? = null
    private var isLoaded = false
    
    // Maintain compatibility with existing calls
    fun getSafeEngine(): Any? = tts
    fun isInitialized() = isLoaded

    fun preloadBoth(context: Context, onComplete: (() -> Unit)? = null) {
        if (tts != null) {
            onComplete?.invoke()
            return
        }
        
        Log.d(TAG, "Initializing Native Android TTS...")
        tts = TextToSpeech(context.applicationContext, this)
        
        // Simulating the callback behavior (OnInitListener calls back asynchronously)
        // We can't guarantee it's ready immediately here, but the listener handles the setup.
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            val result = tts?.setLanguage(Locale.US) // Force English
            
            if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                Log.e(TAG, "English language not supported or missing data")
            } else {
                Log.d(TAG, "Native TTS Initialized Successfully")
                // Optimization: Set speed and pitch for Rafiq-like persona
                tts?.setSpeechRate(0.9f) // Slightly slower for clarity
                tts?.setPitch(1.0f)
                isLoaded = true
            }
        } else {
            Log.e(TAG, "Native TTS Initialization Failed")
        }
    }

    // Stub for compatibility - System TTS switches voices differently
    fun setActiveVoice(voice: String) {
        // In a real implementation, we could look for specific Voices (male/female)
        // tts?.voice = ...
        Log.d(TAG, "Voice switch requested to: $voice (System TTS handles this via default)")
    }

    fun speak(text: String, speed: Float = 1.0f, pitch: Float = 1.0f) {
        if (!isLoaded || tts == null) {
            Log.e(TAG, "TTS not ready yet")
            return
        }
        
        // Apply parameters if needed (Native TTS has global state, so we set it per speak usually)
        tts?.setSpeechRate(speed)
        tts?.setPitch(pitch)
        
        // QUEUE_FLUSH for instant response (interrupts previous speech)
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, null)
    }
    
    fun stop() {
        tts?.stop()
    }
    
    // Cleanup function if needed (e.g. in onDestroy)
    fun shutdown() {
        tts?.shutdown()
        tts = null
        isLoaded = false
    }

    // Stub for unnecessary asset methods
    fun isModelInstalled(context: Context, modelId: String) = true
    fun deleteModel(context: Context, modelId: String) {}
}

package com.example.deliverybot

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.View
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.deliverybot.teleop.CmdVelClient
import android.content.Intent
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech // Import TTS
import java.util.Locale
import androidx.activity.result.contract.ActivityResultContracts
import com.example.deliverybot.net.RosBridgeClient

class ChatActivity : AppCompatActivity() {

    private var speed = 0.5
    private lateinit var cmd: CmdVelClient
    private lateinit var tvCommand1: TextView
    private lateinit var tvCommand2: TextView
    private lateinit var videoWebView: WebView
    private lateinit var speedText: TextView
    private lateinit var seekBarSpeed: SeekBar
    private var responseCallback: ((String) -> Unit)? = null
    
    // TTS
    private lateinit var tts: android.speech.tts.TextToSpeech

    private val commandHistory = mutableListOf<String>()

    private var chatbotDialog: ChatbotBottomSheetDialogFragment? = null

    private val voiceLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == RESULT_OK) {
            val data = result.data
            val matches = data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            if (!matches.isNullOrEmpty()) {
                val spokenText = matches[0]
                chatbotDialog?.updateUserText(spokenText)
                
                if (RosBridgeClient.isConnected()) {
                    chatbotDialog?.updateStatus("Thinking...")
                    RosBridgeClient.publish("/app/chat/request", spokenText)
                } else {
                    val errorMsg = "Not connected to AI"
                    Toast.makeText(this, errorMsg, Toast.LENGTH_SHORT).show()
                    tts.speak(errorMsg, TextToSpeech.QUEUE_FLUSH, null, null)
                    chatbotDialog?.updateStatus("Offline")
                    chatbotDialog?.updateRobotText(errorMsg)
                }
                /*
                // Process command with delay to simulate thinking
                android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                    val response = processVoiceCommand(spokenText)
                    chatbotDialog?.updateRobotText(response)
                    chatbotDialog?.updateStatus("Speaking...")
                }, 1000)
                */
            } else {
                chatbotDialog?.updateStatus("Idle")
            }
        } else {
            chatbotDialog?.updateStatus("Idle")
        }
    }

    private fun log(msg: String) {
        // Add to history, keep only last 2
        commandHistory.add(msg)
        if (commandHistory.size > 2) {
            commandHistory.removeAt(0)
        }
        updateCommandDisplay()
    }

    private fun updateCommandDisplay() {
        val commandSection = findViewById<LinearLayout>(R.id.commandSection)
        
        when (commandHistory.size) {
            0 -> {
                // Hide when no commands
                commandSection.visibility = View.GONE
            }
            1 -> {
                // Show section, display command at bottom (tvCommand1)
                commandSection.visibility = View.VISIBLE
                tvCommand1.text = "Command: ${commandHistory[0]}"
                tvCommand2.visibility = View.GONE
            }
            else -> {
                // Both commands: older at top (tvCommand2), newer at bottom (tvCommand1)
                commandSection.visibility = View.VISIBLE
                tvCommand2.visibility = View.VISIBLE
                tvCommand2.text = "Command: ${commandHistory[0]}"  // Older command
                tvCommand1.text = "Command: ${commandHistory[1]}"  // Newer command
            }
        }
    }

    private fun updateSpeedUI() {
        speedText.text = "Speed: %.1f".format(speed)
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_chat)

        // Initialize TTS
        tts = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts.language = Locale.US
            }
        }

        // Initialize command display
        tvCommand1 = findViewById(R.id.tvCommand1)
        tvCommand2 = findViewById(R.id.tvCommand2)

        // Initialize video using VideoFragment (same as main screen)
        videoWebView = findViewById(R.id.videoWebView)
        setupVideoFragment()

        // Speed controls
        speedText = findViewById(R.id.speedText)
        seekBarSpeed = findViewById(R.id.seekBarSpeed)
        updateSpeedUI()

        seekBarSpeed.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                speed = (progress / 100.0 * 2.0).coerceIn(0.1, 2.0)
                updateSpeedUI()
            }
            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        })

        cmd = CmdVelClient(this)
        cmd.connect()

        // Setup Chatbot Connection
        setupRosSubscription()

        // Direction buttons (now ImageButtons)
        findViewById<ImageButton>(R.id.btnUp).setOnClickListener { 
            log("MOVE_FORWARD")
            cmd.publish(linearX = speed) 
        }
        findViewById<ImageButton>(R.id.btnDown).setOnClickListener { 
            log("MOVE_BACKWARD")
            cmd.publish(linearX = -speed) 
        }
        findViewById<ImageButton>(R.id.btnLeft).setOnClickListener { 
            log("TURN_LEFT")
            cmd.publish(angularZ = speed) 
        }
        findViewById<ImageButton>(R.id.btnRight).setOnClickListener { 
            log("TURN_RIGHT")
            cmd.publish(angularZ = -speed) 
        }
        findViewById<ImageButton>(R.id.btnStop).setOnClickListener { 
            log("STOP")
            cmd.stop() 
        }

        // Voice input
        findViewById<ImageButton>(R.id.btnVoice).setOnClickListener {
            showChatbotDialog()
        }

        // Send button
        findViewById<ImageButton>(R.id.btnSend).setOnClickListener {
            val input = findViewById<EditText>(R.id.messageInput)
            val text = input.text.toString().trim()
            if (text.isNotEmpty()) {
                if (RosBridgeClient.isConnected()) {
                    RosBridgeClient.publish("/app/chat/request", text)
                    Toast.makeText(this, "Sent: $text", Toast.LENGTH_SHORT).show()
                    log("SENT: $text")
                } else {
                    val errorMsg = "⚠️ Not connected to Chatbot"
                    Toast.makeText(this, errorMsg, Toast.LENGTH_SHORT).show()
                    tts.speak("Not connected", TextToSpeech.QUEUE_FLUSH, null, null)
                }
                input.text.clear()
            }
        }
    }

    private var videoFragment: VideoFragment? = null

    private fun setupVideoFragment() {
        // Use VideoFragment - same as main screen
        // Use ConnectionConfig to get correct camera URL (same as main screen)
        val videoUrl = ConnectionConfig.cameraUrl(this)
        
        // Add VideoFragment to container - same as MainActivity
        videoFragment = VideoFragment.newInstance(videoUrl)
        supportFragmentManager.beginTransaction()
            .replace(R.id.videoFragmentContainer, videoFragment!!)
            .commitAllowingStateLoss()
    }

    override fun onResume() {
        super.onResume()
        videoFragment?.reloadVideo()
    }

    override fun onPause() {
        super.onPause()
        videoFragment?.stopVideo()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupVideoStream() {
        videoWebView.visibility = android.view.View.VISIBLE
        videoWebView.settings.javaScriptEnabled = true
        videoWebView.settings.loadWithOverviewMode = true
        videoWebView.settings.useWideViewPort = true
        videoWebView.webViewClient = WebViewClient()

        // Load video stream from ROS web_video_server
        val prefs = getSharedPreferences("app_prefs", MODE_PRIVATE)
        val ip = prefs.getString("ip", "ws://10.42.0.1:9090") ?: "ws://10.42.0.1:9090"
        val baseUrl = ip.replace("ws://", "http://").replace(":9090", ":8080")
        val videoUrl = "$baseUrl/stream?topic=/camera/image_raw"
        
        videoWebView.loadUrl(videoUrl)
    }

    private fun launchVoiceInput() {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak now...")
        }
        try {
            voiceLauncher.launch(intent)
        } catch (e: Exception) {
            Toast.makeText(this, "Voice input not supported", Toast.LENGTH_SHORT).show()
            chatbotDialog?.dismiss()
        }
    }

    private fun showChatbotDialog() {
        chatbotDialog = ChatbotBottomSheetDialogFragment()
        chatbotDialog?.show(supportFragmentManager, "ChatbotDialog")
        
        // Auto-listen when opened
        chatbotDialog?.updateStatus("Listening...")
        // Small delay to let dialog show up
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            launchVoiceInput()
        }, 500)

        chatbotDialog?.onMicToggleListener = {
            chatbotDialog?.updateStatus("Listening...")
            launchVoiceInput()
        }
    }

    private fun processVoiceCommand(text: String): String {
        val lowerText = text.lowercase()
        return when {
            lowerText.contains("forward") || lowerText.contains("أمام") -> {
                log("MOVE_FORWARD")
                cmd.publish(linearX = speed)
                "Moving forward at speed $speed"
            }
            lowerText.contains("back") || lowerText.contains("خلف") -> {
                log("MOVE_BACKWARD")
                cmd.publish(linearX = -speed)
                "Moving backward at speed $speed"
            }
            lowerText.contains("left") || lowerText.contains("يسار") -> {
                log("TURN_LEFT")
                cmd.publish(angularZ = speed)
                "Turning left"
            }
            lowerText.contains("right") || lowerText.contains("يمين") -> {
                log("TURN_RIGHT")
                cmd.publish(angularZ = -speed)
                "Turning right"
            }
            lowerText.contains("stop") || lowerText.contains("قف") -> {
                log("STOP")
                cmd.stop()
                "Stopping robot"
            }
            else -> {
                "I heard: '$text', but I don't know that command yet."
            }
        }
    }

    private fun setupRosSubscription() {
        responseCallback = { response: String ->
            runOnUiThread {
                Toast.makeText(this@ChatActivity, "🤖 $response", Toast.LENGTH_LONG).show()
                chatbotDialog?.updateRobotText(response)
                chatbotDialog?.updateStatus("Idle")
                // Speak the response
                tts.speak(response, TextToSpeech.QUEUE_FLUSH, null, null)
            }
        }
        RosBridgeClient.subscribe("/app/chat/response", responseCallback!!)
    }

    override fun onDestroy() {
        try { cmd.stop() } catch (_: Throwable) {}
        try { cmd.close() } catch (_: Throwable) {}
        responseCallback?.let {
            RosBridgeClient.unsubscribe("/app/chat/response", it)
        }
        if (::tts.isInitialized) {
            tts.stop()
            tts.shutdown()
        }
        super.onDestroy()
    }
}

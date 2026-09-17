package com.example.deliverybot

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import java.text.SimpleDateFormat
import java.util.*
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.result.contract.ActivityResultContracts
import android.widget.LinearLayout
import android.view.Gravity

class RobotAssistantActivity : AppCompatActivity() {
    private lateinit var recyclerViewChat: RecyclerView
    private lateinit var editTextMessage: EditText
    private lateinit var btnSend: ImageButton
    private lateinit var btnMic: ImageButton
    private lateinit var btnBack: ImageButton
    private lateinit var quickActionsContainer: LinearLayout

    private lateinit var chatAdapter: ChatAdapter
    private val messagesList = mutableListOf<ChatMessage>()
    private val chatbotEngine = ChatbotEngine()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_robot_assistant)

        initializeViews()
        setupRecyclerView()
        setupListeners()
        setupQuickActions()
        addBotMessage(chatbotEngine.getWelcomeMessage())
    }

    private val voiceLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == RESULT_OK) {
            val data = result.data
            val matches = data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            if (!matches.isNullOrEmpty()) {
                val spokenText = matches[0]
                editTextMessage.setText(spokenText)
                sendMessage()
            }
        }
    }

    private fun initializeViews() {
        recyclerViewChat = findViewById(R.id.recyclerViewChat)
        editTextMessage = findViewById(R.id.editTextMessage)
        btnSend = findViewById(R.id.btnSend)
        btnMic = findViewById(R.id.btnMic)
        btnBack = findViewById(R.id.btnBack)
        quickActionsContainer = findViewById(R.id.quickActionsContainer)
    }

    private fun setupRecyclerView() {
        chatAdapter = ChatAdapter(messagesList)
        recyclerViewChat.apply {
            adapter = chatAdapter
            layoutManager = LinearLayoutManager(this@RobotAssistantActivity).apply {
                stackFromEnd = true
            }
        }
    }

    private fun setupListeners() {
        btnSend.setOnClickListener { sendMessage() }
        btnBack.setOnClickListener { finish() }
        
        btnMic.setOnClickListener {
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_PROMPT, "Ask the robot...")
            }
            try {
                voiceLauncher.launch(intent)
            } catch (e: Exception) {
                // handle error
            }
        }

        editTextMessage.setOnEditorActionListener { _, _, _ ->
            sendMessage()
            true
        }
    }

    private fun setupQuickActions() {
        val actions = listOf(
            "👥 About Team" to "Who made you?",
            "📊 Analytics" to "Tell me about the dashboard",
            "🧠 Chatbot AI" to "How does the chatbot work?",
            "🤖 Robot Capabilities" to "What can you do?",
            "🗺️ SLAM Mapping" to "Tell me about SLAM mapping",
            "📡 Autonomous Nav" to "How does navigation work?",
            "📹 Live Camera" to "How to watch camera stream?",
            "🎮 Manual Control" to "How to use manual control?",
            "📦 Order Delivery" to "How to create an order?",
            "👍 Gesture AI" to "Tell me about gesture recognition",
            "📷 QR Verification" to "How does QR verification work?",
            "🚧 Obstacle Avoidance" to "How does obstacle avoidance work?"
        )

        for ((label, query) in actions) {
            val chip = android.widget.TextView(this).apply {
                text = label
                setTextColor(android.graphics.Color.WHITE)
                setBackgroundResource(R.drawable.bg_chip_neon) // New Neon Rectangular Background
                // Padding is handled in drawable but we can add extra if needed
                // setPadding(40, 20, 40, 20) 
                textSize = 14f // Larger text
                setTypeface(null, android.graphics.Typeface.BOLD) // Bold text
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply {
                    setMargins(12, 0, 12, 0) // Increased interaction spacing
                }
                setOnClickListener {
                    editTextMessage.setText(query)
                    sendMessage()
                }
            }
            quickActionsContainer.addView(chip)
        }
    }

    private fun sendMessage() {
        val messageText = editTextMessage.text.toString().trim()
        if (messageText.isEmpty()) return

        addUserMessage(messageText)
        editTextMessage.text.clear()

        recyclerViewChat.postDelayed({
            val botResponse = chatbotEngine.getResponse(messageText)
            addBotMessage(botResponse)
        }, 300)
    }

    private fun addUserMessage(message: String) {
        messagesList.add(ChatMessage(message, false, getCurrentTime()))
        chatAdapter.notifyItemInserted(messagesList.size - 1)
        scrollToBottom()
    }

    private fun addBotMessage(message: String) {
        messagesList.add(ChatMessage(message, true, getCurrentTime()))
        chatAdapter.notifyItemInserted(messagesList.size - 1)
        scrollToBottom()
    }

    private fun scrollToBottom() {
        if (messagesList.isNotEmpty()) {
            recyclerViewChat.smoothScrollToPosition(messagesList.size - 1)
        }
    }

    private fun getCurrentTime(): String {
        return SimpleDateFormat("hh:mm a", Locale.getDefault()).format(Date())
    }

    data class ChatMessage(val text: String, val isBot: Boolean, val timestamp: String)

    inner class ChatAdapter(private val messages: List<ChatMessage>) :
        RecyclerView.Adapter<RecyclerView.ViewHolder>() {

        private val VIEW_TYPE_USER = 1
        private val VIEW_TYPE_BOT = 2

        override fun getItemViewType(position: Int) =
            if (messages[position].isBot) VIEW_TYPE_BOT else VIEW_TYPE_USER

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
            return if (viewType == VIEW_TYPE_BOT) {
                val view = LayoutInflater.from(parent.context)
                    .inflate(R.layout.item_bot_message, parent, false)
                BotViewHolder(view)
            } else {
                val view = LayoutInflater.from(parent.context)
                    .inflate(R.layout.item_user_message, parent, false)
                UserViewHolder(view)
            }
        }

        override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
            val msg = messages[position]
            when (holder) {
                is BotViewHolder -> holder.bind(msg)
                is UserViewHolder -> holder.bind(msg)
            }
        }

        override fun getItemCount() = messages.size

        inner class BotViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
            private val textMessage: TextView = itemView.findViewById(R.id.textBotMessage)
            private val textTime: TextView = itemView.findViewById(R.id.textBotTime)
            fun bind(msg: ChatMessage) {
                textMessage.text = msg.text
                textTime.text = msg.timestamp
            }
        }

        inner class UserViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
            private val textMessage: TextView = itemView.findViewById(R.id.textUserMessage)
            private val textTime: TextView = itemView.findViewById(R.id.textUserTime)
            fun bind(msg: ChatMessage) {
                textMessage.text = msg.text
                textTime.text = msg.timestamp
            }
        }
    }
}

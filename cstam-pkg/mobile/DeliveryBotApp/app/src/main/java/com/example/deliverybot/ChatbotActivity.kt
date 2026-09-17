package com.example.deliverybot

import android.content.Intent
import android.os.Bundle
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.drawerlayout.widget.DrawerLayout
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.*
import android.os.Vibrator
import android.os.VibrationEffect
import android.graphics.BitmapFactory
import android.util.Base64
import android.widget.ImageView

/**
 * AI Chat Activity - ROS Llama-powered Chatbot
 * Features: Voice input/output, Chat history drawer, Multiple conversations
 */
class ChatbotActivity : AppCompatActivity(), TextToSpeech.OnInitListener {

    // UI Components
    private lateinit var drawerLayout: DrawerLayout
    private lateinit var recyclerViewChat: RecyclerView
    private lateinit var recyclerViewHistory: RecyclerView
    private lateinit var editTextMessage: EditText
    private lateinit var btnSend: ImageButton
    private lateinit var btnBack: ImageButton
    private lateinit var btnMic: ImageButton
    private lateinit var btnHistory: ImageButton
    private lateinit var btnNewChat: ImageButton
    private lateinit var btnClearHistory: Button
    private lateinit var txtChatTitle: TextView
    private lateinit var txtConnectionStatus: TextView
    private lateinit var btnRobotAssistant: ImageButton
    // private lateinit var btnMap: ImageButton
    private lateinit var btnVoiceToggle: ImageButton
    private lateinit var txtTypingIndicator: TextView 
    
    // Status Chips


    // Haptic
    private lateinit var vibrator: Vibrator

    // Chat Components
    private lateinit var chatAdapter: ChatAdapter
    private val messagesList = mutableListOf<ChatMessage>()
    private val chatbotEngine = ChatbotEngine()

    // Conversation Management
    private var currentConversationId: String = ""
    private val conversations = mutableListOf<Conversation>()
    private lateinit var historyAdapter: HistoryAdapter

    // Text-to-Speech
    private lateinit var tts: TextToSpeech
    private var wasVoiceInput = false
    private var isTtsEnabled = true  // Voice toggle state
    
    // TTS Queue
    private var isTtsReady = false
    private var pendingGreeting: String? = null
    
    // Voice Dialog
    private var voiceDialog: ChatbotBottomSheetDialogFragment? = null

    // SharedPreferences keys
    private val PREFS_NAME = "chat_history"
    private val CONVERSATIONS_KEY = "conversations"

    data class Conversation(
        val id: String,
        var title: String,
        var messages: MutableList<ChatMessage>,
        val timestamp: Long
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_chatbot)

        // Initialize TTS
        tts = TextToSpeech(this, this)
        
        // Initialize Vibrator
        vibrator = getSystemService(VIBRATOR_SERVICE) as Vibrator

        // Initialize views
        initializeViews()
        setupRecyclerView()
        setupHistoryRecyclerView()
        setupListeners()
        setupRosSubscription()

        // Load conversations history
        loadConversations()

        // Update connection status
        updateConnectionStatus()
        
        // Load saved mute preference
        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        isTtsEnabled = !prefs.getBoolean("voice_muted", false)
        updateVoiceToggleIcon()
        
        // Preload BOTH voices FIRST, then start conversation with greeting
        preloadVoicesAndStartGreeting()
    }
    
    /**
     * Preload BOTH voice models at startup, then start conversation with greeting.
     * This ensures voice is ready before speaking.
     */
    private fun preloadVoicesAndStartGreeting() {
        OfflineTtsEngine.preloadBoth(this) {
            runOnUiThread {
                android.util.Log.d("ChatbotActivity", "Both voices preloaded - starting conversation!")
                // NOW start conversation with greeting (voices are ready)
                startNewConversation()
            }
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts.language = Locale.US
            isTtsReady = true
            // Removed: pending greeting fallback - only OfflineTtsEngine speaks
        }
    }

    private fun initializeViews() {
        drawerLayout = findViewById(R.id.drawerLayout)
        recyclerViewChat = findViewById(R.id.recyclerViewChat)
        recyclerViewHistory = findViewById(R.id.recyclerViewHistory)
        editTextMessage = findViewById(R.id.editTextMessage)
        btnSend = findViewById(R.id.btnSend)
        btnBack = findViewById(R.id.btnBack)
        btnMic = findViewById(R.id.btnMic)
        btnHistory = findViewById(R.id.btnHistory)
        btnNewChat = findViewById(R.id.btnNewChat)
        btnClearHistory = findViewById(R.id.btnClearHistory)
        txtChatTitle = findViewById(R.id.txtChatTitle)
        txtConnectionStatus = findViewById(R.id.txtConnectionStatus)
        btnRobotAssistant = findViewById(R.id.btnRobotAssistant)
        // btnMap = findViewById(R.id.btnMap)
        btnVoiceToggle = findViewById(R.id.btnVoiceToggle)
        txtTypingIndicator = findViewById(R.id.txtTypingIndicator)

    }

    private fun setupRecyclerView() {
        chatAdapter = ChatAdapter(messagesList)
        recyclerViewChat.apply {
            adapter = chatAdapter
            layoutManager = LinearLayoutManager(this@ChatbotActivity).apply {
                stackFromEnd = true
            }
        }
    }

    private fun setupHistoryRecyclerView() {
        historyAdapter = HistoryAdapter(
            conversations,
            onClick = { conversation ->
                loadConversation(conversation.id)
                drawerLayout.closeDrawers()
            },
            onDelete = { conversation, position ->
                deleteConversation(conversation, position)
            }
        )
        recyclerViewHistory.apply {
            adapter = historyAdapter
            layoutManager = LinearLayoutManager(this@ChatbotActivity)
        }
    }

    private fun deleteConversation(conv: Conversation, position: Int) {
        // If deleting current conversation, start new one
        if (conv.id == currentConversationId) {
            currentConversationId = ""
            messagesList.clear()
            chatAdapter.notifyDataSetChanged()
            txtChatTitle.text = "AI Chat"
        }
        conversations.removeAt(position)
        historyAdapter.notifyItemRemoved(position)
        saveConversations()
        
        // If no conversations left, start new one
        if (conversations.isEmpty()) {
            startNewConversation()
        }
    }

    private fun setupListeners() {
        btnSend.setOnClickListener { sendMessage() }
        
        btnBack.setOnClickListener {
            saveCurrentConversation()
            // Stop any playing audio when exiting chatbot
            OfflineTtsEngine.stop()
            finish()
        }

        btnMic.setOnClickListener { showVoiceDialog() }

        btnHistory.setOnClickListener {
            if (drawerLayout.isDrawerOpen(android.view.Gravity.END)) {
                drawerLayout.closeDrawer(android.view.Gravity.END)
            } else {
                drawerLayout.openDrawer(android.view.Gravity.END)
            }
        }

        btnNewChat.setOnClickListener {
            saveCurrentConversation()
            startNewConversation()
        }

        btnClearHistory.setOnClickListener {
            conversations.clear()
            saveConversations()
            historyAdapter.notifyDataSetChanged()
            startNewConversation()
            drawerLayout.closeDrawers()
            Toast.makeText(this, "History cleared", Toast.LENGTH_SHORT).show()
        }

        btnRobotAssistant.setOnClickListener {
            startActivity(Intent(this, RobotAssistantActivity::class.java))
        }

        /* btnMap.setOnClickListener {
            startActivity(Intent(this, MapActivity::class.java))
        } */

        btnVoiceToggle.setOnClickListener {
            showVoicePitchDialog()
        }

        btnVoiceToggle.setOnLongClickListener {
            isTtsEnabled = !isTtsEnabled
            updateVoiceToggleIcon()
            val status = if (isTtsEnabled) "Voice ON" else "Voice OFF"
            Toast.makeText(this, status, Toast.LENGTH_SHORT).show()
            true
        }

        editTextMessage.setOnEditorActionListener { _, _, _ ->
            sendMessage()
            true
        }
    }

    // Voice recognition
    private val voiceLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            val results = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            results?.firstOrNull()?.let { spokenText ->
                // Update dialog with user text
                voiceDialog?.updateUserText(spokenText)
                voiceDialog?.updateStatus("Thinking...")
                
                // Send to AI
                editTextMessage.setText(spokenText)
                wasVoiceInput = true
                sendMessage()
            }
        } else {
            voiceDialog?.updateStatus("Idle")
        }
    }

    private fun showVoiceDialog() {
        voiceDialog = ChatbotBottomSheetDialogFragment()
        voiceDialog?.show(supportFragmentManager, "VoiceDialog")
        
        // Auto-start listening when dialog opens
        voiceDialog?.updateStatus("Listening...")
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            startVoiceRecognition()
        }, 500)
        
        // Handle mic toggle button in dialog
        voiceDialog?.onMicToggleListener = {
            voiceDialog?.updateStatus("Listening...")
            startVoiceRecognition()
        }
    }

    private fun startVoiceRecognition() {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ar")
            putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak now...")
        }
        try {
            voiceLauncher.launch(intent)
        } catch (e: Exception) {
            Toast.makeText(this, "Voice input not available", Toast.LENGTH_SHORT).show()
            voiceDialog?.dismiss()
        }
    }

    // ROS Subscription
    private var responseCallback: ((String) -> Unit)? = null

    private fun setupRosSubscription() {
        responseCallback = { response: String ->
            runOnUiThread {
                try {
                    // Try to parse JSON for dual-language support
                    val json = JSONObject(response)
                    val displayText = json.getString("text")
                    val voiceText = json.optString("voice", "") // Optional voice text
                    
                    addBotMessage(displayText)
                    
                    // Update voice dialog if open
                    voiceDialog?.updateRobotText(displayText.take(100))
                    voiceDialog?.updateStatus("Idle")
                    
                    val isTable = displayText.contains("📊") || displayText.startsWith("#")
                    
                    if (isTtsEnabled && !isTable && voiceText.isNotEmpty() && OfflineTtsEngine.getSafeEngine() != null) {
                        // Speak English Voice Text
                        OfflineTtsEngine.speak(voiceText, speed = 1.0f, pitch = 1.0f)
                    } else if (isTtsEnabled && !isTable && OfflineTtsEngine.getSafeEngine() != null) {
                         // Fallback: Speak display text if no specific voice text
                        val cleanText = displayText.replace(Regex("[^\\p{L}\\p{N}\\p{P}\\p{Z}]"), "")
                        OfflineTtsEngine.speak(cleanText, speed = 1.0f, pitch = 1.0f)
                    }
                    
                    // Haptic Feedback for Motion - check both texts
                    if (displayText.contains("[ACTION:") || displayText.contains("FORWARD") || displayText.contains("BACKWARD") || displayText.contains("تحرك")) {
                        vibratePhone()
                    }
                    
                } catch (e: Exception) {
                    // FALLBACK: Old format (Plain Text) or JSON parse error
                    addBotMessage(response)
                    
                    // Update voice dialog if open (fallback)
                    voiceDialog?.updateRobotText(response.take(100))
                    voiceDialog?.updateStatus("Idle")
                    
                    val isTable = response.contains("📊") || response.startsWith("#")
                    
                    // SAFETY: Only speak if the text is English (ASCII). 
                    // Speaking Arabic to the English model causes native crashes.
                    val isEnglish = response.matches(Regex("^[\\x00-\\x7F]*$"))
                    
                    if (isTtsEnabled && !isTable && isEnglish && OfflineTtsEngine.getSafeEngine() != null) {
                        OfflineTtsEngine.speak(response, speed = 1.0f, pitch = 1.0f)
                    }
                    
                    if (response.contains("[ACTION:") || response.contains("FORWARD") || response.contains("BACKWARD")) {
                        vibratePhone()
                    }
                }
                
                wasVoiceInput = false
                txtTypingIndicator.visibility = View.GONE  // Hide typing indicator
            }
        }
        com.example.deliverybot.net.RosBridgeClient.subscribe("/app/chat/response", responseCallback!!)
        
        // Status Subscription (Chips Removed)
        com.example.deliverybot.net.RosBridgeClient.subscribe("/app/status") { statusJson ->
            // Logic removed per user request
        }
    }

    private fun updateConnectionStatus() {
        val connected = com.example.deliverybot.net.RosBridgeClient.isConnected()
        val symbol = if (connected) "🟢" else "🔴"
        txtConnectionStatus.text = "$symbol Powered by Rafiq AI"
        txtConnectionStatus.setTextColor(0xFFB0BEC5.toInt())
    }

    private fun updateVoiceToggleIcon() {
        val iconRes = if (isTtsEnabled) 
            android.R.drawable.ic_lock_silent_mode_off
        else 
            android.R.drawable.ic_lock_silent_mode
        btnVoiceToggle.setImageResource(iconRes)
        btnVoiceToggle.imageTintList = android.content.res.ColorStateList.valueOf(
            if (isTtsEnabled) 0xFF00FF88.toInt() else 0xFFFF5555.toInt()
        )
    }

    private fun sendMessage() {
        val messageText = editTextMessage.text.toString().trim()
        if (messageText.isEmpty()) return

        addUserMessage(messageText)
        editTextMessage.text.clear()

        // Update conversation title in HISTORY based on first user message
        // We only update if the title is still the default or generic
        val currentConv = conversations.find { it.id == currentConversationId }
        if (currentConv != null && (currentConv.title == "AI Chat" || currentConv.title == "New Chat")) {
            val title = messageText.take(25) + if (messageText.length > 25) "..." else ""
            currentConv.title = title
            historyAdapter.notifyDataSetChanged()
        }

        // ROS Llama only - no offline fallback
        if (com.example.deliverybot.net.RosBridgeClient.isConnected()) {
            txtTypingIndicator.visibility = View.VISIBLE // Show typing indicator
            com.example.deliverybot.net.RosBridgeClient.publish("/app/chat/request", messageText)
        } else {
            // Show not connected message
            addBotMessage("⚠️ Not connected to AI server. Please run ./app on your computer and ensure you're on the same network.")
        }
    }

    private fun vibratePhone() {
        if (android.os.Build.VERSION.SDK_INT >= 26) {
            vibrator.vibrate(VibrationEffect.createOneShot(200, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            vibrator.vibrate(200)
        }
    }

    private fun addUserMessage(message: String) {
        val chatMessage = ChatMessage(message, false, getCurrentTime())
        messagesList.add(chatMessage)
        chatAdapter.notifyItemInserted(messagesList.size - 1)
        scrollToBottom()
        saveCurrentConversation()
    }

    private fun addBotMessage(message: String) {
        val chatMessage = ChatMessage(message, true, getCurrentTime())
        messagesList.add(chatMessage)
        chatAdapter.notifyItemInserted(messagesList.size - 1)
        scrollToBottom()
        saveCurrentConversation()
    }

    private fun showVoicePitchDialog() {
        val dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_voice_settings, null)
        
        // Voice selection
        val radioGroup = dialogView.findViewById<android.widget.RadioGroup>(R.id.radioGroupVoice)
        val radioMale = dialogView.findViewById<android.widget.RadioButton>(R.id.radioMale)
        val radioFemale = dialogView.findViewById<android.widget.RadioButton>(R.id.radioFemale)
        
        // Mute switch
        val switchMute = dialogView.findViewById<androidx.appcompat.widget.SwitchCompat>(R.id.switchMute)
        
        // Close button
        val btnClose = dialogView.findViewById<Button>(R.id.btnCloseSettings)
        
        // Load saved preferences
        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val selectedVoice = prefs.getString("selected_voice", "male") ?: "male"
        val isMuted = prefs.getBoolean("voice_muted", false)
        
        // Set initial state
        if (selectedVoice == "female") {
            radioFemale.isChecked = true
        } else {
            radioMale.isChecked = true
        }
        switchMute.isChecked = isMuted
        isTtsEnabled = !isMuted
        
        // Voice selection change - INSTANT switching (models already preloaded)
        radioGroup.setOnCheckedChangeListener { _, checkedId ->
            val voice = if (checkedId == R.id.radioFemale) "female" else "male"
            prefs.edit().putString("selected_voice", voice).apply()
            
            // Instant switch (no loading, just pointer change)
            OfflineTtsEngine.setActiveVoice(voice)
            val voiceName = if (voice == "female") "Rafiqa" else "Rafiq"
            Toast.makeText(this, "Voice changed to $voiceName", Toast.LENGTH_SHORT).show()
        }
        
        // Mute toggle
        switchMute.setOnCheckedChangeListener { _, isChecked ->
            isTtsEnabled = !isChecked
            prefs.edit().putBoolean("voice_muted", isChecked).apply()
            updateVoiceToggleIcon()
            val msg = if (isChecked) "Voice muted" else "Voice enabled"
            Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
        }
        
        val dialog = androidx.appcompat.app.AlertDialog.Builder(this)
            .setView(dialogView)
            .create()
        
        dialog.window?.setBackgroundDrawableResource(android.R.color.transparent)
        
        btnClose.setOnClickListener { dialog.dismiss() }
        
        dialog.show()
    }

    private fun scrollToBottom() {
        if (messagesList.isNotEmpty()) {
            recyclerViewChat.smoothScrollToPosition(messagesList.size - 1)
        }
    }

    private fun getCurrentTime(): String {
        return SimpleDateFormat("hh:mm a", Locale.getDefault()).format(Date())
    }

    // Conversation Management
    private fun startNewConversation() {
        saveCurrentConversation()
        currentConversationId = UUID.randomUUID().toString()
        messagesList.clear()
        chatAdapter.notifyDataSetChanged()
        txtChatTitle.text = "AI Chat"

        val newConv = Conversation(
            id = currentConversationId,
            title = "AI Chat",
            messages = mutableListOf(),
            timestamp = System.currentTimeMillis()
        )
        conversations.add(0, newConv)
        historyAdapter.notifyDataSetChanged()
        saveConversations()

        // Get selected voice from preferences
        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val selectedVoice = prefs.getString("selected_voice", "male") ?: "male"
        
        // Set greeting based on selected voice
        val (arabicText, englishVoice) = if (selectedVoice == "female") {
            Pair(
                "مرحباً! أنا رفيقة، مساعدتك الذكية. كيف يمكنني مساعدتك اليوم؟",
                "Hello! I am Rafiqa, your smart delivery assistant. How can I help you today?"
            )
        } else {
            Pair(
                "مرحباً! أنا رفيق، مساعدك الذكي. كيف يمكنني مساعدتك اليوم؟",
                "Hello! I am Rafiq, your smart delivery assistant. How can I help you today?"
            )
        }
        
        addBotMessage(arabicText)
        
        // Speak greeting using OfflineTtsEngine ONLY (no system TTS fallback)
        if (isTtsEnabled && OfflineTtsEngine.getSafeEngine() != null) {
            OfflineTtsEngine.speak(englishVoice, speed = 1.0f, pitch = 1.0f)
        }
    }

    private fun loadConversation(id: String) {
        saveCurrentConversation()
        currentConversationId = id
        val conv = conversations.find { it.id == id } ?: return

        messagesList.clear()
        messagesList.addAll(conv.messages)
        chatAdapter.notifyDataSetChanged()
        txtChatTitle.text = "AI Chat"
        scrollToBottom()
    }

    private fun saveCurrentConversation() {
        if (currentConversationId.isEmpty()) return
        val conv = conversations.find { it.id == currentConversationId } ?: return
        conv.messages.clear()
        conv.messages.addAll(messagesList)
        saveConversations()
    }

    private fun saveConversations() {
        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val jsonArray = JSONArray()
        conversations.forEach { conv ->
            // FILTER: Only save if there are user messages OR more than just the greeting
            // We assume the first message is always the bot greeting.
            // So if size <= 1 and that one message is from bot, consider it empty.
            if (conv.messages.size > 1 || (conv.messages.isNotEmpty() && !conv.messages[0].isBot)) {
               val convObj = JSONObject().apply {
                    put("id", conv.id)
                    put("title", conv.title)
                    put("timestamp", conv.timestamp)
                    val messagesArray = JSONArray()
                    conv.messages.forEach { msg ->
                        val msgObj = JSONObject().apply {
                            put("text", msg.text)
                            put("isBot", msg.isBot)
                            put("timestamp", msg.timestamp)
                        }
                        messagesArray.put(msgObj)
                    }
                    put("messages", messagesArray)
                }
                jsonArray.put(convObj)
            }
        }
        prefs.edit().putString(CONVERSATIONS_KEY, jsonArray.toString()).apply()
    }

    private fun loadConversations() {
        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val json = prefs.getString(CONVERSATIONS_KEY, null) ?: return
        try {
            val jsonArray = JSONArray(json)
            conversations.clear()
            for (i in 0 until jsonArray.length()) {
                val convObj = jsonArray.getJSONObject(i)
                val messagesArray = convObj.getJSONArray("messages")
                val messages = mutableListOf<ChatMessage>()
                for (j in 0 until messagesArray.length()) {
                    val msgObj = messagesArray.getJSONObject(j)
                    messages.add(ChatMessage(
                        text = msgObj.getString("text"),
                        isBot = msgObj.getBoolean("isBot"),
                        timestamp = msgObj.getString("timestamp")
                    ))
                }
                conversations.add(Conversation(
                    id = convObj.getString("id"),
                    title = convObj.getString("title"),
                    messages = messages,
                    timestamp = convObj.getLong("timestamp")
                ))
            }
            historyAdapter.notifyDataSetChanged()
        } catch (e: Exception) {
            // Ignore
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        saveCurrentConversation()
        // Stop and cleanup all audio
        OfflineTtsEngine.stop()
        tts.stop()
        tts.shutdown()
        responseCallback?.let {
            com.example.deliverybot.net.RosBridgeClient.unsubscribe("/app/chat/response", it)
        }
    }
    
    override fun onPause() {
        super.onPause()
        // Stop audio when app goes to background or activity changes
        OfflineTtsEngine.stop()
    }

    // Chat Message Data Class
    data class ChatMessage(val text: String, val isBot: Boolean, val timestamp: String)

    // Chat Adapter
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
            private val imageSnapshot: ImageView = itemView.findViewById(R.id.imageBotSnapshot)

            fun bind(msg: ChatMessage) {
                if (msg.text.startsWith("[IMAGE:")) {
                    try {
                        val base64 = msg.text.substringAfter("[IMAGE:").substringBefore("]")
                        val decodedString = Base64.decode(base64, Base64.DEFAULT)
                        val decodedByte = BitmapFactory.decodeByteArray(decodedString, 0, decodedString.size)
                        imageSnapshot.setImageBitmap(decodedByte)
                        imageSnapshot.visibility = View.VISIBLE
                        
                        val remainingText = msg.text.substringAfter("]").trim()
                        if (remainingText.isNotEmpty()) {
                            textMessage.text = remainingText
                            textMessage.visibility = View.VISIBLE
                        } else {
                            textMessage.visibility = View.GONE
                        }
                    } catch (e: Exception) {
                         textMessage.text = "⚠️ Error loading image"
                         textMessage.visibility = View.VISIBLE
                         imageSnapshot.visibility = View.GONE
                    }
                } else {
                    imageSnapshot.visibility = View.GONE
                    textMessage.visibility = View.VISIBLE
                    textMessage.text = msg.text
                }
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

    // History Adapter
    inner class HistoryAdapter(
        private val items: MutableList<Conversation>,
        private val onClick: (Conversation) -> Unit,
        private val onDelete: (Conversation, Int) -> Unit
    ) : RecyclerView.Adapter<HistoryAdapter.ViewHolder>() {

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
            val view = LayoutInflater.from(parent.context)
                .inflate(R.layout.item_conversation, parent, false)
            return ViewHolder(view)
        }

        override fun onBindViewHolder(holder: ViewHolder, position: Int) {
            holder.bind(items[position], position)
        }

        override fun getItemCount() = items.size

        inner class ViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
            private val txtTitle: TextView = itemView.findViewById(R.id.txtConversationTitle)
            private val txtPreview: TextView = itemView.findViewById(R.id.txtConversationPreview)
            private val txtTime: TextView = itemView.findViewById(R.id.txtConversationTime)
            private val btnDelete: ImageButton = itemView.findViewById(R.id.btnDeleteConversation)

            fun bind(conv: Conversation, position: Int) {
                txtTitle.text = conv.title
                txtPreview.text = conv.messages.lastOrNull()?.text ?: "No messages"
                txtTime.text = getRelativeTime(conv.timestamp)
                itemView.setOnClickListener { onClick(conv) }
                btnDelete.setOnClickListener { 
                    val currentPos = adapterPosition
                    if (currentPos != RecyclerView.NO_POSITION) {
                        onDelete(items[currentPos], currentPos) 
                    }
                }
            }

            private fun getRelativeTime(timestamp: Long): String {
                val diff = System.currentTimeMillis() - timestamp
                return when {
                    diff < 60000 -> "Just now"
                    diff < 3600000 -> "${diff / 60000} min ago"
                    diff < 86400000 -> "${diff / 3600000} hours ago"
                    else -> SimpleDateFormat("MMM dd", Locale.getDefault()).format(Date(timestamp))
                }
            }
        }
    }
}
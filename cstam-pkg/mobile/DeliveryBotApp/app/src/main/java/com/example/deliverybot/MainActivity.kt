package com.example.deliverybot

// Imports for core Android components
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.Button
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.viewpager2.widget.ViewPager2

// Imports for permission handling
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

// Imports for other activities and RosBridge client
import com.example.deliverybot.OrdersActivity
import com.example.deliverybot.ChatActivity
import com.example.deliverybot.CameraActivity
import com.example.deliverybot.net.RosBridgeClient


/**
 * Helper object for saving and retrieving IP configuration.
 */
object Prefs {
    private const val PREFS_FILE = "app"
    private const val IP_KEY = "ip"
    private const val DEFAULT_IP = "ws://10.42.0.1:9090"

    fun saveIp(ctx: Context, ip: String) {
        ctx.getSharedPreferences(PREFS_FILE, Context.MODE_PRIVATE).edit()
            .putString(IP_KEY, ip).apply()
    }

    fun getIp(ctx: Context): String =
        ctx.getSharedPreferences(PREFS_FILE, Context.MODE_PRIVATE)
            .getString(IP_KEY, DEFAULT_IP) ?: DEFAULT_IP
    
    fun getRawIp(ctx: Context): String {
        val full = getIp(ctx)
        return full.replace("ws://", "").replace("wss://", "").replace(":9090", "")
    }
}

/**
 * The main activity of the application, serving as the dashboard for navigation
 * and connection setup.
 */
class MainActivity : AppCompatActivity() {

    // Top Bar
    private lateinit var btnConnect: ImageButton
    private lateinit var btnSettings: ImageButton
    private lateinit var txtStatus: TextView

    // ViewPager for Video/Dashboard swipe
    private lateinit var viewPager: ViewPager2
    private lateinit var pagerAdapter: MainPagerAdapter

    // Control Grid Cards
    private lateinit var cardOpenMap: LinearLayout
    private lateinit var cardDashboard: LinearLayout
    private lateinit var cardChatbot: LinearLayout
    private lateinit var cardManualControl: LinearLayout

    // Primary Button
    private lateinit var btnCreateOrder: Button

    // URLs
    private var mjpegUrl: String = "http://10.42.0.1:8080/stream?topic=/camera/image_raw"
    private var dashboardUrl: String = "http://10.42.0.1:8501"

    private val NOTIFICATION_CHANNEL_ID = "delivery_bot_channel"
    private val CAMERA_PERMISSION_REQUEST_CODE = 100
    private val POST_NOTIFICATIONS_REQUEST_CODE = 101

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Apply Dark Mode preference
        val prefs = getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        val isDarkMode = prefs.getBoolean("dark_mode", true)
        if (isDarkMode) {
            androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_YES)
        } else {
            androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_NO)
        }

        setContentView(R.layout.activity_main)

        createNotificationChannel()
        bindViews()
        setupViewPager()
        setupClickListeners()
        setupNotifications()
        updateStatusDisplay()

        // Request POST_NOTIFICATIONS permission on Android 13+
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(
                    arrayOf(android.Manifest.permission.POST_NOTIFICATIONS),
                    POST_NOTIFICATIONS_REQUEST_CODE
                )
            }
        }

        // Start preloading TTS voices immediately so they are ready for Chatbot
        OfflineTtsEngine.preloadBoth(this)
    }

    private fun bindViews() {
        // Top Bar
        btnConnect = findViewById(R.id.btnConnect)
        btnSettings = findViewById(R.id.btnSettings)
        txtStatus = findViewById(R.id.txtStatus)

        // ViewPager
        viewPager = findViewById(R.id.viewPager)

        // Control Grid
        cardOpenMap = findViewById(R.id.cardOpenMap)
        cardDashboard = findViewById(R.id.cardDashboard)
        cardChatbot = findViewById(R.id.cardChatbot)
        cardManualControl = findViewById(R.id.cardManualControl)

        // Primary Button
        btnCreateOrder = findViewById(R.id.btnCreateOrder)
    }

    private fun setupViewPager() {
        // Build URLs based on saved IP
        val ip = Prefs.getRawIp(this)
        mjpegUrl = "http://$ip:8080/stream?topic=/camera/image_raw"
        dashboardUrl = "http://$ip:8501"

        pagerAdapter = MainPagerAdapter(this, mjpegUrl, dashboardUrl)
        viewPager.adapter = pagerAdapter
        
        // Start on Dashboard (index 0), swipe right for Camera (index 1)
        // Actually let's start with Camera (index 0) and swipe for Dashboard
        viewPager.setCurrentItem(0, false)
    }

    private fun setupClickListeners() {
        // Connect Button - Opens ScanActivity for device discovery
        btnConnect.setOnClickListener {
            startScanAndConnect()
        }

        // Settings Button
        btnSettings.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }

        // Open Map Card
        cardOpenMap.setOnClickListener {
            if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.CAMERA)
                != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this,
                    arrayOf(android.Manifest.permission.CAMERA), CAMERA_PERMISSION_REQUEST_CODE)
            } else {
                openMapActivity()
            }
        }

        // Dashboard Card - Opens Streamlit Dashboard inside the app
        cardDashboard.setOnClickListener {
            val intent = Intent(this, DashboardActivity::class.java)
            intent.putExtra(DashboardActivity.EXTRA_DASHBOARD_URL, dashboardUrl)
            startActivity(intent)
        }

        // AI Chatbot Card
        cardChatbot.setOnClickListener {
            startActivity(Intent(this, ChatbotActivity::class.java))
        }

        // Manual Control Card - Stop main video before opening
        cardManualControl.setOnClickListener {
            pagerAdapter.stopVideo()  // Stop video in main screen
            startActivity(Intent(this, ChatActivity::class.java))
        }

        // Create New Order Button
        btnCreateOrder.setOnClickListener {
            startActivity(Intent(this, AddressActivity::class.java))
        }
    }

    /**
     * Initiates connection to RosBridge or opens ScanActivity for device discovery.
     */
    private fun startScanAndConnect() {
        val ipRaw = Prefs.getRawIp(this).ifBlank { "10.42.0.1" }

        // Construct WebSocket URL
        val url = "wss://$ipRaw:9090"

        // Show connecting progress dialog
        val progress = android.app.ProgressDialog(this).apply {
            setMessage("Connecting to ROS Bridge...")
            setCancelable(false)
            show()
        }

        val wasConnected = RosBridgeClient.isConnected()
        var ignoreDisconnect = wasConnected
        var isHandled = false

        val listener = object : (Boolean) -> Unit {
            override fun invoke(connected: Boolean) {
                if (isHandled) return

                if (!connected && ignoreDisconnect) {
                    ignoreDisconnect = false
                    return
                }

                isHandled = true
                runOnUiThread {
                    try { progress.dismiss() } catch(_: Throwable){}
                    RosBridgeClient.removeConnectionListener(this)
                    if (connected) {
                        Toast.makeText(this@MainActivity, "Connected to ROS: $url", Toast.LENGTH_SHORT).show()
                        updateStatusDisplay()
                    } else {
                        Toast.makeText(this@MainActivity, "Connection failed. Scanning...", Toast.LENGTH_SHORT).show()
                        startActivity(Intent(this@MainActivity, ScanActivity::class.java))
                    }
                }
            }
        }
        RosBridgeClient.addConnectionListener(listener)
        RosBridgeClient.connect(url)

        // Timeout handler
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            if (!isHandled) {
                isHandled = true
                try { progress.dismiss() } catch(_: Throwable){}
                RosBridgeClient.removeConnectionListener(listener)
                Toast.makeText(this, "Connection timed out. Scanning...", Toast.LENGTH_SHORT).show()
                startActivity(Intent(this, ScanActivity::class.java))
            }
        }, 5000)
    }

    private fun updateStatusDisplay() {
        val ip = Prefs.getRawIp(this)
        val connected = RosBridgeClient.isConnected()
        val statusEmoji = if (connected) "🟢" else "🔴"
        val statusText = if (connected) "Online" else "Offline"
        txtStatus.text = "$statusEmoji $statusText | $ip"
    }

    override fun onResume() {
        super.onResume()
        updateStatusDisplay()
        
        // Refresh URLs in case IP changed
        val ip = Prefs.getRawIp(this)
        mjpegUrl = "http://$ip:8080/stream?topic=/camera/image_raw"
        dashboardUrl = "http://$ip:8501"
        pagerAdapter.updateVideoUrl(mjpegUrl)
        pagerAdapter.updateDashboardUrl(dashboardUrl)
        pagerAdapter.startVideo() // Resume video when returning to main screen
    }

    // Listener to handle ROS bridge connection status updates
    private val connectionListener: (Boolean) -> Unit = { connected ->
        runOnUiThread { updateStatusDisplay() }
        if (shouldNotify()) {
            val msg = if (connected) "Connected to Robot 🤖" else "Disconnected from Robot ❌"
            showNotification("ROS Connection Status", msg)
        }
    }

    private fun setupNotifications() {
        RosBridgeClient.addConnectionListener(connectionListener)

        try {
            RosBridgeClient.subscribe("/app/goal_status") { msg ->
                if (shouldNotify()) {
                    val lower = msg.lowercase()
                    if (lower.contains("arrived") ||
                        lower.contains("goal reached") ||
                        lower.contains("succeeded")) {
                        showNotification("Robot Update", "The robot has arrived! 🏁")
                    }
                }
            }
        } catch (_: Throwable) {
            Log.w("MainActivity", "Failed to subscribe to goal status topic")
        }
    }

    private fun shouldNotify(): Boolean {
        val prefs = getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        return prefs.getBoolean("notifications_enabled", true)
    }

    private fun showNotification(title: String, content: String) {
        runOnUiThread {
            Toast.makeText(this, "$title: $content", Toast.LENGTH_SHORT).show()

            val builder = androidx.core.app.NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(title)
                .setContentText(content)
                .setPriority(androidx.core.app.NotificationCompat.PRIORITY_DEFAULT)
                .setAutoCancel(true)

            with(androidx.core.app.NotificationManagerCompat.from(this)) {
                try {
                    notify(System.currentTimeMillis().toInt(), builder.build())
                } catch (e: SecurityException) {
                    Log.e("MainActivity", "Notification permission missing: ${e.message}")
                }
            }
        }
    }

    private fun createNotificationChannel() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            val name = "DeliveryBot Notifications"
            val descriptionText = "Notifications for robot status updates"
            val importance = android.app.NotificationManager.IMPORTANCE_DEFAULT
            val channel = android.app.NotificationChannel(NOTIFICATION_CHANNEL_ID, name, importance).apply {
                description = descriptionText
            }
            val notificationManager: android.app.NotificationManager =
                getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        RosBridgeClient.removeConnectionListener(connectionListener)
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)

        when (requestCode) {
            CAMERA_PERMISSION_REQUEST_CODE -> {
                if (grantResults.isNotEmpty() &&
                    grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                    openMapActivity()
                } else {
                    Toast.makeText(
                        this,
                        "Camera permission is required to use the map.",
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
            POST_NOTIFICATIONS_REQUEST_CODE -> {
                if (grantResults.isNotEmpty() &&
                    grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                    Log.d("MainActivity", "Notification permission granted")
                } else {
                    Log.d("MainActivity", "Notification permission denied")
                }
            }
        }
    }

    private fun openMapActivity() {
        val intent = Intent(this, MapActivity::class.java)
        startActivity(intent)
    }
}
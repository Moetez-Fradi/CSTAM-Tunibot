package com.example.deliverybot

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class OrdersActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_orders)

        val container = findViewById<android.widget.LinearLayout>(R.id.historyContainer)
        val tvNoHistory = findViewById<android.widget.TextView>(R.id.tvNoHistory)

        val prefs = getSharedPreferences("app_prefs", MODE_PRIVATE)
        val history = prefs.getString("order_history", "") ?: ""

        if (history.isBlank()) {
            tvNoHistory.visibility = android.view.View.VISIBLE
        } else {
            tvNoHistory.visibility = android.view.View.GONE
            // History format: "timestamp|destination;timestamp|destination;..."
            // We want newest first, so split, reverse, then iterate
            val items = history.split(";").reversed()
            
            for (item in items) {
                if (item.isBlank()) continue
                val parts = item.split("|")
                if (parts.size >= 2) {
                    val timestamp = parts[0]
                    val destination = parts[1]
                    val qrPath = if (parts.size >= 3) parts[2] else ""
                    addHistoryItem(container, timestamp, destination, qrPath)
                }
            }
        }
    }

    private fun addHistoryItem(container: android.widget.LinearLayout, timestamp: String, destination: String, qrPath: String) {
        val card = android.widget.LinearLayout(this)
        card.orientation = android.widget.LinearLayout.VERTICAL
        card.background = androidx.core.content.ContextCompat.getDrawable(this, R.drawable.bg_card_dark)
        card.setPadding(30, 30, 30, 30)
        val params = android.widget.LinearLayout.LayoutParams(
            android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
            android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
        )
        params.setMargins(0, 0, 0, 20)
        card.layoutParams = params

        val tvDest = android.widget.TextView(this)
        tvDest.text = "Destination: $destination"
        tvDest.textSize = 18f
        tvDest.setTypeface(null, android.graphics.Typeface.BOLD)
        tvDest.setTextColor(androidx.core.content.ContextCompat.getColor(this, R.color.text_primary))
        
        val tvTime = android.widget.TextView(this)
        tvTime.text = timestamp
        tvTime.textSize = 14f
        tvTime.setTextColor(androidx.core.content.ContextCompat.getColor(this, R.color.text_secondary))
        tvTime.setPadding(0, 8, 0, 0)

        card.addView(tvDest)
        card.addView(tvTime)
        container.addView(card)

        // Click listener for details
        card.setOnClickListener {
            showOrderDetails(destination, timestamp, qrPath)
        }
    }

    private fun showOrderDetails(destination: String, timestamp: String, qrPath: String) {
        val builder = androidx.appcompat.app.AlertDialog.Builder(this)
        builder.setTitle("Order Details")

        val layout = android.widget.LinearLayout(this)
        layout.orientation = android.widget.LinearLayout.VERTICAL
        layout.setPadding(50, 50, 50, 50)
        layout.gravity = android.view.Gravity.CENTER_HORIZONTAL
        // Ensure background is dark/light based on theme so text is visible
        layout.background = androidx.core.content.ContextCompat.getDrawable(this, R.color.bg_dark)

        val tvInfo = android.widget.TextView(this)
        tvInfo.text = "Destination: $destination\nTime: $timestamp"
        tvInfo.textSize = 16f
        tvInfo.gravity = android.view.Gravity.CENTER
        tvInfo.setTextColor(androidx.core.content.ContextCompat.getColor(this, R.color.text_primary)) // Ensure visibility
        layout.addView(tvInfo)

        if (qrPath.isNotBlank()) {
            val qrFile = java.io.File(qrPath)
            if (qrFile.exists()) {
                val bmp = android.graphics.BitmapFactory.decodeFile(qrPath)
                if (bmp != null) {
                    val iv = android.widget.ImageView(this)
                    val lp = android.widget.LinearLayout.LayoutParams(500, 500)
                    lp.topMargin = 30
                    iv.layoutParams = lp
                    iv.setImageBitmap(bmp)
                    layout.addView(iv)
                }
            } else {
                val tvErr = android.widget.TextView(this)
                tvErr.text = "\n(QR Code file not found)"
                tvErr.setTextColor(android.graphics.Color.RED)
                layout.addView(tvErr)
            }
        } else {
            val tvErr = android.widget.TextView(this)
            tvErr.text = "\n(No QR Code saved)"
            tvErr.setTextColor(android.graphics.Color.GRAY)
            layout.addView(tvErr)
        }

        builder.setView(layout)
        builder.setPositiveButton("Close", null)
        builder.show()
    }
}

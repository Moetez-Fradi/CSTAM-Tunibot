package com.example.deliverybot

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

object Prefs {
    fun saveIp(ctx: Context, ip: String) {
        ctx.getSharedPreferences("app", Context.MODE_PRIVATE).edit()
            .putString("ip", ip).apply()
    }
    fun getIp(ctx: Context): String =
        ctx.getSharedPreferences("app", Context.MODE_PRIVATE)
            .getString("ip", "10.42.0.1") ?: "10.42.0.1"
}

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val ipEdit = findViewById<EditText>(R.id.ipEdit)
        ipEdit.setText(Prefs.getIp(this))

        findViewById<Button>(R.id.btnSave).setOnClickListener {
            val ip = ipEdit.text.toString().trim()
            Prefs.saveIp(this, ip)
            Toast.makeText(this, "Saved IP: $ip", Toast.LENGTH_SHORT).show()
        }

        findViewById<Button>(R.id.btnOrders).setOnClickListener {
            startActivity(Intent(this, OrdersActivity::class.java))
        }
        findViewById<Button>(R.id.btnChat).setOnClickListener {
            startActivity(Intent(this, ChatActivity::class.java))
        }
        findViewById<Button>(R.id.btnMap).setOnClickListener {
            startActivity(Intent(this, MapActivity::class.java))
        }
        findViewById<Button>(R.id.btnCamera).setOnClickListener {
            Toast.makeText(this, "Open Camera coming soon", Toast.LENGTH_SHORT).show()
        }
    }
}

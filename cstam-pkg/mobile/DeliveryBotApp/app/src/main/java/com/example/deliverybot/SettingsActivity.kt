package com.example.deliverybot

import android.content.Context
import android.os.Bundle
import android.widget.Switch
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate

class SettingsActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        val switchDarkMode = findViewById<Switch>(R.id.switchDarkMode)
        val switchNotifications = findViewById<Switch>(R.id.switchNotifications)

        val prefs = getSharedPreferences("app_prefs", Context.MODE_PRIVATE)

        // Load current state
        val isDarkMode = prefs.getBoolean("dark_mode", true) // Default to dark? Or system?
        val areNotificationsEnabled = prefs.getBoolean("notifications_enabled", true)

        switchDarkMode.isChecked = isDarkMode
        switchNotifications.isChecked = areNotificationsEnabled

        switchDarkMode.setOnCheckedChangeListener { _, isChecked ->
            prefs.edit().putBoolean("dark_mode", isChecked).apply()
            applyDarkMode(isChecked)
        }

        switchNotifications.setOnCheckedChangeListener { _, isChecked ->
            prefs.edit().putBoolean("notifications_enabled", isChecked).apply()
        }
    }

    private fun applyDarkMode(isDark: Boolean) {
        if (isDark) {
            AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_YES)
        } else {
            AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_NO)
        }
    }
}

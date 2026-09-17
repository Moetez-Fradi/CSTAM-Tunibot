package com.example.deliverybot

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.ImageView
import android.widget.TextView
import com.google.android.material.bottomsheet.BottomSheetDialogFragment

class ChatbotBottomSheetDialogFragment : BottomSheetDialogFragment() {

    private lateinit var tvStatus: TextView
    private lateinit var ivStatusIcon: ImageView
    private lateinit var tvUserText: TextView
    private lateinit var tvRobotText: TextView
    private lateinit var btnMicToggle: Button
    private lateinit var btnClose: Button

    var onMicToggleListener: (() -> Unit)? = null

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        return inflater.inflate(R.layout.fragment_chatbot_dialog, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        tvStatus = view.findViewById(R.id.tvStatus)
        ivStatusIcon = view.findViewById(R.id.ivStatusIcon)
        tvUserText = view.findViewById(R.id.tvUserText)
        tvRobotText = view.findViewById(R.id.tvRobotText)
        btnMicToggle = view.findViewById(R.id.btnMicToggle)
        btnClose = view.findViewById(R.id.btnClose)

        btnClose.setOnClickListener {
            dismiss()
        }

        btnMicToggle.setOnClickListener {
            onMicToggleListener?.invoke()
        }
    }

    fun updateStatus(status: String) {
        if (!isAdded) return
        activity?.runOnUiThread {
            tvStatus.text = status
            when (status) {
                "Listening..." -> {
                    ivStatusIcon.setImageResource(android.R.drawable.ic_btn_speak_now)
                    ivStatusIcon.setColorFilter(0xFF00D9FF.toInt()) // Cyan
                    btnMicToggle.text = "Stop Listening"
                    btnMicToggle.background.setTint(0xFFFF3B3B.toInt()) // Red
                }
                "Thinking..." -> {
                    ivStatusIcon.setImageResource(android.R.drawable.ic_popup_sync)
                    ivStatusIcon.setColorFilter(0xFFFFA500.toInt()) // Orange
                    btnMicToggle.isEnabled = false
                }
                "Speaking..." -> {
                    ivStatusIcon.setImageResource(android.R.drawable.ic_lock_silent_mode_off)
                    ivStatusIcon.setColorFilter(0xFF00FF00.toInt()) // Green
                    btnMicToggle.isEnabled = true
                    btnMicToggle.text = "Listen Again"
                    btnMicToggle.background.setTint(0xFF00D9FF.toInt()) // Cyan
                }
                else -> { // Idle
                    ivStatusIcon.setImageResource(android.R.drawable.ic_btn_speak_now)
                    ivStatusIcon.setColorFilter(0xFF888888.toInt()) // Grey
                    btnMicToggle.text = "Start Listening"
                    btnMicToggle.background.setTint(0xFF00D9FF.toInt()) // Cyan
                }
            }
        }
    }

    fun updateUserText(text: String) {
        if (!isAdded) return
        activity?.runOnUiThread {
            tvUserText.text = "You: $text"
        }
    }

    fun updateRobotText(text: String) {
        if (!isAdded) return
        activity?.runOnUiThread {
            tvRobotText.text = "Robot: $text"
        }
    }
}

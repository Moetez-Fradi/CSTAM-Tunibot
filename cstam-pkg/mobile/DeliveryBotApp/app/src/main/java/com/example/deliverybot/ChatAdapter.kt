package com.example.deliverybot

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

data class ChatMessage(val sender: String, val body: String)

class ChatAdapter : RecyclerView.Adapter<ChatAdapter.VH>() {
    private val data = mutableListOf<ChatMessage>()

    fun add(m: ChatMessage) {
        data.add(m)
        notifyItemInserted(data.lastIndex)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_chat_message, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) = holder.bind(data[position])
    override fun getItemCount(): Int = data.size

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        private val tvSender = v.findViewById<TextView>(R.id.tvSender)
        private val tvBody = v.findViewById<TextView>(R.id.tvBody)
        fun bind(m: ChatMessage) {
            tvSender.text = m.sender
            tvBody.text = m.body
        }
    }
}

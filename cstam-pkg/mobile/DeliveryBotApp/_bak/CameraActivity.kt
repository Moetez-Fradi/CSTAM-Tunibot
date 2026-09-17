package com.example.deliverybot

import android.net.Uri
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.google.android.exoplayer2.ExoPlayer
import com.google.android.exoplayer2.MediaItem
import com.google.android.exoplayer2.ui.StyledPlayerView

class CameraActivity : AppCompatActivity() {
    private lateinit var playerView: StyledPlayerView
    private var player: ExoPlayer? = null
    private var rtspUrl: String = "rtsp://127.0.0.1:8554/stream"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_camera)
        playerView = findViewById(R.id.playerView)
        intent.getStringExtra("rtspUrl")?.let { rtspUrl = it }
    }

    private fun initPlayer() {
        player = ExoPlayer.Builder(this).build().also { p ->
            playerView.player = p
            p.setMediaItem(MediaItem.fromUri(Uri.parse(rtspUrl)))
            p.prepare()
            p.playWhenReady = true
        }
    }

    private fun releasePlayer() {
        playerView.player = null
        player?.release()
        player = null
    }

    override fun onStart() { super.onStart(); if (player == null) initPlayer() }
    override fun onStop() { super.onStop(); releasePlayer() }
}

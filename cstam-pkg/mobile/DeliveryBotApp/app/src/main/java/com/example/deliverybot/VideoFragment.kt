package com.example.deliverybot

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ProgressBar
import android.widget.TextView
import androidx.fragment.app.Fragment

/**
 * Fragment displaying the live camera feed from the robot.
 * Loads MJPEG stream via WebView.
 */
class VideoFragment : Fragment() {

    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var errorText: TextView
    
    private var videoUrl: String = ""

    companion object {
        private const val ARG_URL = "video_url"
        
        fun newInstance(url: String): VideoFragment {
            return VideoFragment().apply {
                arguments = Bundle().apply {
                    putString(ARG_URL, url)
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        videoUrl = arguments?.getString(ARG_URL) ?: ""
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        return inflater.inflate(R.layout.fragment_video, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        
        webView = view.findViewById(R.id.videoWebView)
        progressBar = view.findViewById(R.id.videoProgress)
        errorText = view.findViewById(R.id.txtVideoError)

        setupWebView()
        loadVideo()
        
        // Tap overlay to open fullscreen camera
        val clickOverlay = view.findViewById<View>(R.id.videoClickOverlay)
        clickOverlay.setOnClickListener {
            openFullscreen()
        }
        
        // Tap error text to retry
        errorText.setOnClickListener {
            loadVideo()
        }
    }

    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            loadWithOverviewMode = true
            useWideViewPort = true
            cacheMode = WebSettings.LOAD_NO_CACHE
        }
        
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                progressBar.visibility = View.GONE
                errorText.visibility = View.GONE
            }
            
            override fun onReceivedError(
                view: WebView?,
                errorCode: Int,
                description: String?,
                failingUrl: String?
            ) {
                progressBar.visibility = View.GONE
                errorText.visibility = View.VISIBLE
            }
        }
    }

    private fun loadVideo() {
        if (videoUrl.isNotEmpty()) {
            progressBar.visibility = View.VISIBLE
            errorText.visibility = View.GONE
            // Load MJPEG stream in an img tag for simplicity
            val html = """
                <html>
                <body style="margin:0;padding:0;background:#000;">
                <img src="$videoUrl" style="width:100%;height:100%;object-fit:contain;"/>
                </body>
                </html>
            """.trimIndent()
            webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null)
        } else {
            errorText.text = "No video URL configured"
            errorText.visibility = View.VISIBLE
            progressBar.visibility = View.GONE
        }
    }

    private fun openFullscreen() {
        // Launch CameraActivity for fullscreen view
        val intent = android.content.Intent(requireContext(), CameraActivity::class.java)
        intent.putExtra("mjpegUrl", videoUrl)
        startActivity(intent)
    }

    fun updateUrl(newUrl: String) {
        videoUrl = newUrl
        if (::webView.isInitialized) {
            loadVideo()
        }
    }

    fun stopVideo() {
        if (::webView.isInitialized) {
            webView.loadUrl("about:blank")
        }
    }

    fun reloadVideo() {
        if (::webView.isInitialized && videoUrl.isNotEmpty()) {
            loadVideo()
        }
    }
}

package com.example.deliverybot

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity

class MapActivity : AppCompatActivity() {
    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Get the ROS WebSocket URL from the project's configuration
        // Create ROS WebSocket URL dynamically
        val wsUrl = try { 
             com.example.deliverybot.ConnectionConfig.rosbridgeWs(this) 
        } catch (e: Throwable) {
             "ws://10.42.0.1:9090" // Fallback
        }

        web = WebView(this).apply {
            // Enable JavaScript for ROS communication
            settings.javaScriptEnabled = true
            settings.cacheMode = WebSettings.LOAD_NO_CACHE
            settings.domStorageEnabled = true
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = true
            try { settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW } catch (_: Throwable) {}
            webViewClient = object : WebViewClient() {
                @SuppressLint("WebViewClientOnReceivedSslError")
                override fun onReceivedSslError(view: WebView, handler: android.webkit.SslErrorHandler, error: android.net.http.SslError) {
                    handler.proceed()
                }
            }
        }
        setContentView(web)

        // The full HTML content for the WebView, displaying ONLY the map
        val html = """
            <!doctype html>
            <html>
            <head>
              <meta name='viewport' content='width=device-width, initial-scale=1.0'>
              <style>
                /* Full screen fill */
                html, body {
                  height: 100vh; width: 100vw;
                  margin: 0; background: #000;
                  display: flex; align-items: center; justify-content: center;
                }
                /* Map Canvas */
                #c {
                  max-width: 95vw;
                  max-height: 95vh;
                  width: auto; height: auto;
                  image-rendering: pixelated; /* Crisp map pixels */
                  background: #111;
                }
              </style>
            </head>
            <body>
              <canvas id="c"></canvas>
              
              <script>
                const wsUrl = ${'"'}$wsUrl${'"'};
                const mapTopic = "/map";
                const waypointsTopic = "/app/map/waypoints";

                const ws = new WebSocket(wsUrl.replace(/^http/i, "ws"));
                
                let mapInfo = null; // Store map resolution/origin
                let waypoints = []; // Store waypoints data
                let mapImage = null; // Store map image data
                
                // ---------------- ROS MAP HANDLING LOGIC ----------------
                ws.onopen = () => {
                    // Subscribe to the map topic
                    ws.send(JSON.stringify({op:"subscribe", topic: mapTopic, type:"nav_msgs/OccupancyGrid"}));
                    // Subscribe to Waypoints from ChatBridge
                    ws.send(JSON.stringify({op:"subscribe", topic: waypointsTopic, type:"std_msgs/String"}));
                    console.log("ROS WebSocket connected.");
                };
                
                ws.onmessage = (ev) => {
                  const m = JSON.parse(ev.data);
                  // HANDLE WAYPOINTS
                  if (m.topic === waypointsTopic) {
                      waypoints = JSON.parse(m.msg.data);
                      draw(); // Redraw with new waypoints
                      return;
                  }
                  
                  // HANDLE MAP
                  if (m.topic === mapTopic) {
                      const msg = m.msg;
                      const w = msg.info.width|0;
                      const h = msg.info.height|0;
                      
                      // Normalize Origin (Handle negative zeros or missing fields)
                      mapInfo = {
                          res: msg.info.resolution,
                          originX: msg.info.origin.position.x,
                          originY: msg.info.origin.position.y,
                          width: w,
                          height: h
                      };

                      const data = msg.data;
                      const c = document.getElementById("c");
                      if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
                      
                      const ctx = c.getContext("2d");
                      // Store raw image data to redraw later
                      mapImage = ctx.createImageData(w, h);
                      
                      for (let y=0; y<h; y++) for (let x=0; x<w; x++) {
                        const v = data[y*w + x];
                        const g = (v < 0) ? 127 : Math.max(0, Math.min(255, 255 - Math.round(255*(v/100))));
                        // Flip Y axis for Canvas (ROS 0,0 is bottom-left, Canvas 0,0 is top-left)
                        const yy = (h-1-y), i = (yy*w + x)*4;
                        mapImage.data[i]=g; mapImage.data[i+1]=g; mapImage.data[i+2]=g; mapImage.data[i+3]=255;
                      }
                      draw();
                  }
                };
                
                function draw() {
                    const c = document.getElementById("c");
                    const ctx = c.getContext("2d");
                    
                    // 1. Draw Map
                    if (mapImage) {
                        ctx.putImageData(mapImage, 0, 0);
                    }
                    
                    // 2. Draw Waypoints
                    if (mapInfo && waypoints.length > 0) {
                        // Dynamic sizing based on map width (heuristic)
                        // If map is 2000px wide, we want ~20px text.
                        const scale = Math.max(1, mapInfo.width / 100); 
                        const fontSize = Math.max(15, scale * 1.5);
                        const radius = Math.max(5, scale * 0.4);

                        ctx.font = `bold ${'$'}{fontSize}px Arial`;
                        ctx.fillStyle = "red";
                        ctx.textAlign = "center";
                        ctx.textBaseline = "bottom"; // Text above dot
                        
                        waypoints.forEach(wp => {
                            // Convert World -> Pixel
                            const px = (wp.x - mapInfo.originX) / mapInfo.res;
                            const py = mapInfo.height - ((wp.y - mapInfo.originY) / mapInfo.res);
                            
                            // Draw Dot
                            ctx.beginPath();
                            ctx.arc(px, py, radius, 0, 2 * Math.PI);
                            ctx.fill();
                            
                            // Draw Label
                            ctx.fillStyle = "cyan";
                            // Add stroke to make text readable on white/black
                            ctx.strokeStyle = "black";
                            ctx.lineWidth = radius / 4;
                            ctx.strokeText(wp.name, px, py - radius);
                            ctx.fillText(wp.name, px, py - radius);
                            
                            ctx.fillStyle = "red"; // Reset for next dot
                        });
                    }
                }
                // ---------------- END OF ROS MAP HANDLING LOGIC ----------------

              </script>
            </body>
            </html>
        """.trimIndent()

        web.loadDataWithBaseURL(null, html, "text/html", "utf-8", null)
    }

    override fun onDestroy() { try { web.destroy() } catch (_: Throwable) {}; super.onDestroy() }
}

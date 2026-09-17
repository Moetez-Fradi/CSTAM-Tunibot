package com.example.deliverybot

import android.content.Context
import android.net.wifi.WifiManager
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.*
import java.net.InetAddress
import java.net.Inet4Address
import java.net.NetworkInterface
import java.net.InetSocketAddress
import java.net.Socket

data class Device(val ip: String, val name: String)

class ScanActivity : AppCompatActivity() {

    private lateinit var adapter: DeviceAdapter
    private val devices = mutableListOf<Device>()
    private var scanJob: Job? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_scan)

        val recycler = findViewById<RecyclerView>(R.id.recyclerDevices)
        recycler.layoutManager = LinearLayoutManager(this)
        adapter = DeviceAdapter(devices) { device ->
            // On Click
            Prefs.saveIp(this, device.ip)
            setResult(RESULT_OK)
            finish()
        }
        recycler.adapter = adapter

        findViewById<View>(R.id.btnCancel).setOnClickListener {
            setResult(RESULT_CANCELED)
            finish()
        }

        startScan()
    }

    private fun startScan() {
        scanJob?.cancel()
        devices.clear()
        adapter.notifyDataSetChanged()
        findViewById<View>(R.id.progressBar).visibility = View.VISIBLE

        scanJob = CoroutineScope(Dispatchers.IO).launch {
            try {
                // Collect all local IPs to identify possible subnets
                val  localIps = mutableSetOf<String>()

                // 1. Try WifiManager (Good for Client mode)
                val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
                if (wifiManager != null) {
                     val dhcpInfo = wifiManager.dhcpInfo
                     if (dhcpInfo != null && dhcpInfo.ipAddress != 0) {
                         localIps.add(formatIp(dhcpInfo.ipAddress))
                     }
                }
                
                // 2. Try NetworkInterfaces (Good for Hotspot Host mode & Fallback)
                val interfaceIps = getLocalIpAddresses()
                localIps.addAll(interfaceIps)

                if (localIps.isEmpty()) {
                     withContext(Dispatchers.Main) {
                        android.widget.Toast.makeText(this@ScanActivity, "Could not determine any Device IP", android.widget.Toast.LENGTH_SHORT).show()
                        findViewById<View>(R.id.progressBar).visibility = View.GONE
                    }
                    return@launch
                }
                
                // Identify unique subnets (e.g. 192.168.43. and 10.0.0.)
                val subnets = localIps.map { it.substringBeforeLast(".") + "." }.distinct()
                
                // Scan all subnets in parallel
                val allJobs = mutableListOf<Deferred<Unit>>()

                for (subnet in subnets) {
                    val subnetJobs = (1..254).map { i ->
                        async {
                            val targetIp = "$subnet$i"
                            // Skip our own IPs to avoid confusion (optional, but good practice)
                            if (localIps.contains(targetIp)) return@async
                            
                            try {
                                val socket = Socket()
                                socket.connect(InetSocketAddress(targetIp, 9090), 500)
                                socket.close()
                                
                                val name = try {
                                    InetAddress.getByName(targetIp).canonicalHostName
                                } catch (e: Exception) { targetIp }
                                
                                withContext(Dispatchers.Main) {
                                    // Avoid duplicates in UI
                                    if (devices.none { it.ip == targetIp }) {
                                        devices.add(Device(targetIp, name))
                                        adapter.notifyItemInserted(devices.size - 1)
                                    }
                                }
                            } catch (e: Exception) {
                                // Not found
                            }
                        }
                    }
                    allJobs.addAll(subnetJobs)
                }
                allJobs.awaitAll()
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    android.widget.Toast.makeText(this@ScanActivity, "Scan error: ${e.message}", android.widget.Toast.LENGTH_SHORT).show()
                }
            } finally {
                withContext(Dispatchers.Main) {
                    findViewById<View>(R.id.progressBar).visibility = View.GONE
                    if (devices.isEmpty()) {
                        android.widget.Toast.makeText(this@ScanActivity, "No devices found", android.widget.Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }
    }

    private fun formatIp(ip: Int): String {
        return "${ip and 0xFF}.${(ip shr 8) and 0xFF}.${(ip shr 16) and 0xFF}.${(ip shr 24) and 0xFF}"
    }

    private fun getLocalIpAddresses(): List<String> {
         val ips = mutableListOf<String>()
         try {
             val en = NetworkInterface.getNetworkInterfaces()
             while (en.hasMoreElements()) {
                 val intf = en.nextElement()
                 val enumIpAddr = intf.inetAddresses
                 while (enumIpAddr.hasMoreElements()) {
                     val inetAddress = enumIpAddr.nextElement()
                     if (!inetAddress.isLoopbackAddress && inetAddress is Inet4Address) {
                         ips.add(inetAddress.hostAddress ?: "")
                     }
                 }
             }
         } catch (ex: Exception) {
             ex.printStackTrace()
         }
         return ips.filter { it.isNotEmpty() }
    }
    
    override fun onDestroy() {
        super.onDestroy()
        scanJob?.cancel()
    }
}

class DeviceAdapter(private val list: List<Device>, private val onClick: (Device) -> Unit) : RecyclerView.Adapter<DeviceAdapter.VH>() {
    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val text: TextView = v.findViewById(android.R.id.text1)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(android.R.layout.simple_list_item_1, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val d = list[position]
        holder.text.text = "${d.name}\n${d.ip}"
        holder.text.setTextColor(android.graphics.Color.WHITE)
        holder.itemView.setOnClickListener { onClick(d) }
    }

    override fun getItemCount() = list.size
}

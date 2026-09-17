package com.example.deliverybot

import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.viewpager2.adapter.FragmentStateAdapter

/**
 * Adapter for the ViewPager2 that holds Video and Dashboard fragments.
 * Swipe left/right to switch between them.
 */
class MainPagerAdapter(
    activity: FragmentActivity,
    private val videoUrl: String,
    private val dashboardUrl: String
) : FragmentStateAdapter(activity) {

    private var videoFragment: VideoFragment? = null
    private var dashboardFragment: DashboardFragment? = null

    override fun getItemCount(): Int = 2

    override fun createFragment(position: Int): Fragment {
        return when (position) {
            0 -> {
                videoFragment = VideoFragment.newInstance(videoUrl)
                videoFragment!!
            }
            1 -> {
                dashboardFragment = DashboardFragment.newInstance(dashboardUrl)
                dashboardFragment!!
            }
            else -> throw IllegalArgumentException("Invalid position: $position")
        }
    }

    fun updateVideoUrl(newUrl: String) {
        videoFragment?.updateUrl(newUrl)
    }

    fun updateDashboardUrl(newUrl: String) {
        dashboardFragment?.updateUrl(newUrl)
    }

    fun stopVideo() {
        videoFragment?.stopVideo()
    }

    fun startVideo() {
        videoFragment?.reloadVideo()
    }
}

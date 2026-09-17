package com.example.deliverybot

object OrderPublisher {
    fun advertiseOrderTopic(): String =
        """{"op":"advertise","topic":"/order/json","type":"std_msgs/String"}"""

    fun publishOrder(orderId: String, phone: String, address: String, wp: String? = null,
                     x: Double? = null, y: Double? = null, theta: Double? = null): String {
        val payload = if (wp != null)
            """{"order_id":"$orderId","phone":"$phone","address":"$address","waypoint":"$wp"}"""
        else
            """{"order_id":"$orderId","phone":"$phone","address":"$address","x":$x,"y":$y,"theta":$theta}"""
        val esc = payload.replace("\"", "\\\"")
        return """{"op":"publish","topic":"/order/json","msg":{"data":"$esc"}}"""
    }

    fun callGenerateQr(orderId: String, phone: String, address: String): String =
        """{"op":"call_service","service":"/generate_qr","id":"qr1",
            "args":{"order_id":"$orderId","phone":"$phone","address":"$address"}}""".trimIndent()
}

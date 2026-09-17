# Helper for R8/Proguard
-keep class com.k2fsa.sherpa.onnx.** { *; }
-keep class com.example.deliverybot.** { *; }
-keepattributes *Annotation*
-keepattributes Signature
-keepattributes InnerClasses
-keepattributes EnclosingMethod

# Javascript Interface (if used)
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# Coroutines
-keep class kotlinx.coroutines.** { *; }

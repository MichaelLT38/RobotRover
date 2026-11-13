plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.bitswizzler.robotrover"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.bitswizzler.robotrover"
        minSdk = 26          // Android 8.0+
        targetSdk = 35
        versionCode = 3
        versionName = "1.3"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    // Name the APK RobotRover.apk (RobotRover-release.apk for release builds)
    // instead of Gradle's default app-debug.apk
    applicationVariants.all {
        val suffix = if (buildType.name == "debug") "" else "-${buildType.name}"
        outputs.all {
            (this as com.android.build.gradle.internal.api.BaseVariantOutputImpl).outputFileName = "RobotRover$suffix.apk"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

// No third-party libraries: only the Android SDK and the Kotlin standard library.
dependencies {
}

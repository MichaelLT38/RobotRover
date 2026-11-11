package com.bitswizzler.robotrover

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.bluetooth.BluetoothAdapter
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.SeekBar
import android.widget.TextView

class MainActivity : Activity(), RobotBle.Listener {

    companion object {
        private const val REQUEST_PERMISSIONS = 1

        // While a drive button is held, send a short drive pulse this often.
        // Each pulse lasts DRIVE_PULSE_MS on the robot, so if the connection
        // drops the robot stops on its own within a fraction of a second.
        private const val DRIVE_REPEAT_MS = 150L
        private const val DRIVE_PULSE_MS = 400

        // Don't flood the robot while dragging a slider
        private const val SLIDER_SEND_INTERVAL_MS = 100L
        private const val LOG_LINES = 6

        // Must match the sketch's home positions
        private const val HOME_BASE = 90
        private const val HOME_SHOULDER = 90
        private const val HOME_ELBOW = 90
        private const val GRIPPER_OPEN = 30
        private const val GRIPPER_CLOSED = 120
    }

    private lateinit var robot: RobotBle
    private lateinit var connectButton: Button
    private lateinit var statusText: TextView
    private lateinit var statusDot: View
    private lateinit var statusPillText: TextView
    private lateinit var controls: ViewGroup
    private lateinit var logText: TextView
    private lateinit var btnOpen: TextView
    private lateinit var btnClose: TextView
    private lateinit var seekBase: SeekBar
    private lateinit var seekShoulder: SeekBar
    private lateinit var seekElbow: SeekBar
    private lateinit var seekGrip: SeekBar

    private val main = Handler(Looper.getMainLooper())
    private val logLines = ArrayDeque<String>()
    private var heldDriveCommand: String? = null

    private val driveRepeater = object : Runnable {
        override fun run() {
            val cmd = heldDriveCommand ?: return
            robot.send("$cmd $DRIVE_PULSE_MS", kind = "drive")
            main.postDelayed(this, DRIVE_REPEAT_MS)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        robot = RobotBle(this, this)

        connectButton = findViewById(R.id.connectButton)
        statusText = findViewById(R.id.statusText)
        statusDot = findViewById(R.id.statusDot)
        statusPillText = findViewById(R.id.statusPillText)
        controls = findViewById(R.id.controls)
        logText = findViewById(R.id.logText)
        btnOpen = findViewById(R.id.btnOpen)
        btnClose = findViewById(R.id.btnClose)
        seekBase = findViewById(R.id.seekBase)
        seekShoulder = findViewById(R.id.seekShoulder)
        seekElbow = findViewById(R.id.seekElbow)
        seekGrip = findViewById(R.id.seekGrip)

        connectButton.setOnClickListener {
            if (robot.state == RobotBle.State.OFFLINE) {
                startConnecting()
            } else {
                stopDriving()
                robot.disconnect()
                statusText.text = "Disconnected"
            }
        }

        // Drive pad
        setupDriveButton(R.id.btnForward, "w")
        setupDriveButton(R.id.btnBack, "s")
        setupDriveButton(R.id.btnLeft, "a")
        setupDriveButton(R.id.btnRight, "d")
        findViewById<View>(R.id.btnStop).setOnClickListener { stopDriving() }

        setupSlider(findViewById(R.id.seekSpeed), findViewById(R.id.speedPill), "speed") { "Speed $it" }

        // Arm
        setupSlider(seekBase, findViewById(R.id.valueBase), "base") { "$it°" }
        setupSlider(seekShoulder, findViewById(R.id.valueShoulder), "shoulder") { "$it°" }
        setupSlider(seekElbow, findViewById(R.id.valueElbow), "elbow") { "$it°" }
        setupSlider(seekGrip, findViewById(R.id.valueGrip), "grip") { "$it°" }

        btnOpen.setOnClickListener {
            robot.send("open", kind = "grip")
            seekGrip.progress = GRIPPER_OPEN
        }
        btnClose.setOnClickListener {
            robot.send("close", kind = "grip")
            seekGrip.progress = GRIPPER_CLOSED
        }
        findViewById<View>(R.id.btnHome).setOnClickListener {
            robot.send("home")
            seekBase.progress = HOME_BASE
            seekShoulder.progress = HOME_SHOULDER
            seekElbow.progress = HOME_ELBOW
            seekGrip.progress = GRIPPER_OPEN
        }

        // The relay shuts the board's Linux side down, so the battery can be switched off safely
        findViewById<View>(R.id.powerOffButton).setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("Power off the robot?")
                .setMessage("The board shuts down. Switch the battery off when the LED matrix shows the sleeping face.")
                .setPositiveButton("Power off") { _, _ ->
                    stopDriving()
                    robot.send("poweroff")
                }
                .setNegativeButton("Cancel", null)
                .show()
        }

        updateGripperToggle(seekGrip.progress)
        onStateChanged(RobotBle.State.OFFLINE)
    }

    override fun onPause() {
        super.onPause()
        // Safety: never keep driving if the app goes to the background
        stopDriving()
    }

    override fun onDestroy() {
        stopDriving()
        robot.disconnect()
        super.onDestroy()
    }

    // ------------------------------------------------------------------
    //  Controls
    // ------------------------------------------------------------------

    @SuppressLint("ClickableViewAccessibility")
    private fun setupDriveButton(id: Int, command: String) {
        findViewById<View>(id).setOnTouchListener { view, event ->
            if (!view.isEnabled) return@setOnTouchListener true
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    view.isPressed = true      // lights the button orange while held
                    startDriving(command)
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    view.isPressed = false
                    stopDriving()
                }
            }
            true
        }
    }

    private fun startDriving(command: String) {
        heldDriveCommand = command
        main.removeCallbacks(driveRepeater)
        driveRepeater.run()
    }

    private fun stopDriving() {
        heldDriveCommand = null
        main.removeCallbacks(driveRepeater)
        robot.send("x", kind = "drive")   // does nothing if not connected
    }

    /** Slider that sends "<command> <value>" while dragging (throttled) and when released. */
    private fun setupSlider(seekBar: SeekBar, valueView: TextView, command: String, format: (Int) -> String) {
        var lastSent = 0L
        valueView.text = format(seekBar.progress)

        seekBar.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(bar: SeekBar, value: Int, fromUser: Boolean) {
                valueView.text = format(value)
                if (bar == seekGrip) updateGripperToggle(value)
                if (!fromUser) return
                val now = SystemClock.uptimeMillis()
                if (now - lastSent >= SLIDER_SEND_INTERVAL_MS) {
                    lastSent = now
                    robot.send("$command $value", kind = command)
                }
            }

            override fun onStartTrackingTouch(bar: SeekBar) {}

            override fun onStopTrackingTouch(bar: SeekBar) {
                robot.send("$command ${bar.progress}", kind = command)
            }
        })
    }

    /** Highlights Open or Close depending on which end the gripper is nearer. */
    private fun updateGripperToggle(angle: Int) {
        val open = angle < (GRIPPER_OPEN + GRIPPER_CLOSED) / 2
        btnOpen.isSelected = open
        btnClose.isSelected = !open
    }

    // ------------------------------------------------------------------
    //  Bluetooth permissions + connecting
    // ------------------------------------------------------------------

    private fun neededPermissions(): Array<String> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }

    @SuppressLint("MissingPermission")   // permissions are checked just above
    private fun startConnecting() {
        val missing = neededPermissions().filter {
            checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            requestPermissions(missing.toTypedArray(), REQUEST_PERMISSIONS)
            return
        }
        if (!robot.isBluetoothOn) {
            statusText.text = "Turn on Bluetooth, then tap connect again"
            startActivity(Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE))
            return
        }
        robot.connect()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != REQUEST_PERMISSIONS) return
        if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
            startConnecting()
        } else {
            statusText.text = "Bluetooth permission is needed to talk to the robot"
        }
    }

    // ------------------------------------------------------------------
    //  RobotBle.Listener
    // ------------------------------------------------------------------

    override fun onStatus(text: String) {
        statusText.text = text
    }

    override fun onReply(text: String) {
        logLines.addLast(text.trim())
        while (logLines.size > LOG_LINES) logLines.removeFirst()

        // Newest reply in bright text with a marker, older ones grey
        val out = SpannableStringBuilder()
        logLines.forEachIndexed { i, line ->
            if (i > 0) out.append("\n")
            val newest = i == logLines.size - 1
            val start = out.length
            out.append(if (newest) "› $line" else "  $line")
            if (newest) {
                out.setSpan(
                    ForegroundColorSpan(getColor(R.color.text)),
                    start, out.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE,
                )
            }
        }
        logText.text = out
    }

    override fun onStateChanged(state: RobotBle.State) {
        val (label, dotColor) = when (state) {
            RobotBle.State.OFFLINE -> "Offline" to R.color.status_offline
            RobotBle.State.SEARCHING -> "Searching…" to R.color.status_busy
            RobotBle.State.CONNECTING -> "Connecting…" to R.color.status_busy
            RobotBle.State.CONNECTED -> "Connected" to R.color.status_ok
        }
        statusPillText.text = label
        statusDot.backgroundTintList = ColorStateList.valueOf(getColor(dotColor))

        // Orange "Connect" button when offline, quiet outline button otherwise
        if (state == RobotBle.State.OFFLINE) {
            connectButton.text = "Connect to robot"
            connectButton.setBackgroundResource(R.drawable.bg_button_primary)
            connectButton.setTextColor(getColor(R.color.on_accent))
        } else {
            connectButton.text = if (state == RobotBle.State.CONNECTED) "Disconnect" else "Cancel"
            connectButton.setBackgroundResource(R.drawable.bg_button_outline)
            connectButton.setTextColor(getColor(R.color.text))
        }

        val connected = state == RobotBle.State.CONNECTED
        if (!connected) {
            heldDriveCommand = null
            main.removeCallbacks(driveRepeater)
        }
        controls.alpha = if (connected) 1f else 0.4f
        setEnabledDeep(controls, connected)
    }

    private fun setEnabledDeep(view: View, enabled: Boolean) {
        view.isEnabled = enabled
        if (view is ViewGroup) {
            for (i in 0 until view.childCount) setEnabledDeep(view.getChildAt(i), enabled)
        }
    }
}

package com.bitswizzler.robotrover

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import java.util.UUID

/**
 * Talks to the robot over Bluetooth LE (Nordic UART Service).
 * Commands are plain text like "w 300" or "base 45"; replies come back as text.
 *
 * Android only allows one Bluetooth operation at a time, so commands go through a
 * small queue. Commands with the same "kind" (e.g. two pending "base" moves) are
 * merged so the robot always gets the latest value instead of a backlog.
 *
 * Callers must have Bluetooth permissions before calling connect().
 */
@SuppressLint("MissingPermission")
class RobotBle(private val context: Context, private val listener: Listener) {

    enum class State { OFFLINE, SEARCHING, CONNECTING, CONNECTED }

    interface Listener {
        fun onStatus(text: String)
        fun onReply(text: String)
        fun onStateChanged(state: State)
    }

    companion object {
        const val DEVICE_NAME = "RobotRover"
        val SERVICE_UUID: UUID = UUID.fromString("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
        val RX_UUID: UUID = UUID.fromString("6e400002-b5a3-f393-e0a9-e50e24dcca9e")  // we write here
        val TX_UUID: UUID = UUID.fromString("6e400003-b5a3-f393-e0a9-e50e24dcca9e")  // robot replies here
        val CCCD_UUID: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
        private const val SCAN_TIMEOUT_MS = 10_000L
        private const val MAX_QUEUE = 20
        private const val REQUESTED_MTU = 185
    }

    private data class Pending(val kind: String, val command: String)

    private val main = Handler(Looper.getMainLooper())
    private val adapter: BluetoothAdapter? =
        (context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter

    private var gatt: BluetoothGatt? = null
    private var rxCharacteristic: BluetoothGattCharacteristic? = null
    private var scanning = false
    private val queue = ArrayDeque<Pending>()
    private var operationInFlight = false

    var state = State.OFFLINE
        private set

    val isConnected: Boolean
        get() = state == State.CONNECTED

    val isBluetoothOn: Boolean
        get() = adapter?.isEnabled == true

    // ------------------------------------------------------------------
    //  Public API (call from the main thread)
    // ------------------------------------------------------------------

    fun connect() {
        disconnect()
        val scanner = adapter?.bluetoothLeScanner
        if (scanner == null) {
            listener.onStatus("Bluetooth is off")
            return
        }
        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()
        scanning = true
        scanner.startScan(null, settings, scanCallback)
        main.postDelayed(scanTimeout, SCAN_TIMEOUT_MS)
        setState(State.SEARCHING)
        listener.onStatus("Searching for $DEVICE_NAME…")
    }

    fun disconnect() {
        stopScan()
        queue.clear()
        operationInFlight = false
        gatt?.let {
            it.disconnect()
            it.close()
        }
        gatt = null
        rxCharacteristic = null
        setState(State.OFFLINE)
    }

    /**
     * Queue a command. If [kind] is given, any queued command of the same kind is
     * replaced, so only the newest one is sent.
     */
    fun send(command: String, kind: String = command) {
        if (!isConnected) return
        queue.removeAll { it.kind == kind }
        if (queue.size >= MAX_QUEUE) queue.removeFirst()
        queue.addLast(Pending(kind, command))
        pump()
    }

    // ------------------------------------------------------------------
    //  Scanning
    // ------------------------------------------------------------------

    private val scanTimeout = Runnable {
        if (scanning) {
            stopScan()
            setState(State.OFFLINE)
            listener.onStatus("Robot not found. Is it powered on and the relay running?")
        }
    }

    private fun stopScan() {
        if (!scanning) return
        scanning = false
        main.removeCallbacks(scanTimeout)
        try {
            adapter?.bluetoothLeScanner?.stopScan(scanCallback)
        } catch (e: IllegalStateException) {
            // Bluetooth was turned off mid-scan; nothing to stop
        }
    }

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            main.post { handleScanResult(result) }
        }

        override fun onScanFailed(errorCode: Int) {
            main.post {
                scanning = false
                main.removeCallbacks(scanTimeout)
                setState(State.OFFLINE)
                listener.onStatus("Bluetooth scan failed (error $errorCode)")
            }
        }
    }

    private fun handleScanResult(result: ScanResult) {
        if (!scanning) return
        val record = result.scanRecord
        val hasService = record?.serviceUuids?.any { it.uuid == SERVICE_UUID } == true
        val nameMatches = record?.deviceName == DEVICE_NAME
        if (!hasService && !nameMatches) return

        stopScan()
        setState(State.CONNECTING)
        listener.onStatus("Found robot, connecting…")
        gatt = result.device.connectGatt(context, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
    }

    // ------------------------------------------------------------------
    //  Connection (Android calls these on a background thread; hop to main)
    // ------------------------------------------------------------------

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            main.post {
                if (g != gatt) return@post
                if (newState == BluetoothProfile.STATE_CONNECTED && status == BluetoothGatt.GATT_SUCCESS) {
                    listener.onStatus("Connected, setting up…")
                    // Bigger packets so longer replies fit; services are discovered after this
                    if (!g.requestMtu(REQUESTED_MTU)) g.discoverServices()
                } else {
                    g.close()
                    gatt = null
                    rxCharacteristic = null
                    queue.clear()
                    operationInFlight = false
                    setState(State.OFFLINE)
                    listener.onStatus(
                        if (status == BluetoothGatt.GATT_SUCCESS) "Disconnected"
                        else "Connection lost (error $status). Tap Connect to retry."
                    )
                }
            }
        }

        override fun onMtuChanged(g: BluetoothGatt, mtu: Int, status: Int) {
            main.post { if (g == gatt) g.discoverServices() }
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            main.post {
                if (g != gatt) return@post
                val service = g.getService(SERVICE_UUID)
                val rx = service?.getCharacteristic(RX_UUID)
                if (rx == null) {
                    listener.onStatus("Robot service not found on this device")
                    disconnect()
                    return@post
                }
                rxCharacteristic = rx
                val tx = service.getCharacteristic(TX_UUID)
                if (tx == null || !enableNotifications(g, tx)) {
                    setState(State.CONNECTED)   // works without replies, just no feedback
                }
            }
        }

        override fun onDescriptorWrite(g: BluetoothGatt, descriptor: BluetoothGattDescriptor, status: Int) {
            main.post {
                if (g != gatt) return@post
                operationInFlight = false
                setState(State.CONNECTED)
                pump()
            }
        }

        override fun onCharacteristicWrite(g: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int) {
            main.post {
                if (g != gatt) return@post
                operationInFlight = false
                pump()
            }
        }

        // Android 13+
        override fun onCharacteristicChanged(g: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray) {
            if (characteristic.uuid == TX_UUID) {
                val text = String(value, Charsets.UTF_8)
                main.post { listener.onReply(text) }
            }
        }

        // Android 12 and older
        @Deprecated("Deprecated in Java")
        @Suppress("DEPRECATION")
        override fun onCharacteristicChanged(g: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU && characteristic.uuid == TX_UUID) {
                val text = String(characteristic.value ?: ByteArray(0), Charsets.UTF_8)
                main.post { listener.onReply(text) }
            }
        }
    }

    /** Turns on reply notifications. Returns true if the request was sent. */
    @Suppress("DEPRECATION")
    private fun enableNotifications(g: BluetoothGatt, tx: BluetoothGattCharacteristic): Boolean {
        g.setCharacteristicNotification(tx, true)
        val cccd = tx.getDescriptor(CCCD_UUID) ?: return false
        val sent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            g.writeDescriptor(cccd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE) == BluetoothStatusCodes.SUCCESS
        } else {
            cccd.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            g.writeDescriptor(cccd)
        }
        if (sent) operationInFlight = true
        return sent
    }

    // ------------------------------------------------------------------
    //  Sending
    // ------------------------------------------------------------------

    @Suppress("DEPRECATION")
    private fun pump() {
        if (operationInFlight || !isConnected) return
        val g = gatt ?: return
        val rx = rxCharacteristic ?: return
        val next = queue.removeFirstOrNull() ?: return

        val bytes = (next.command + "\n").toByteArray(Charsets.UTF_8)
        val sent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            g.writeCharacteristic(rx, bytes, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT) ==
                BluetoothStatusCodes.SUCCESS
        } else {
            rx.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
            rx.value = bytes
            g.writeCharacteristic(rx)
        }

        if (sent) {
            operationInFlight = true
        } else {
            // Bluetooth stack was busy; try again shortly
            queue.addFirst(next)
            main.postDelayed({ pump() }, 50)
        }
    }

    private fun setState(newState: State) {
        if (state == newState) return
        state = newState
        listener.onStateChanged(newState)
        if (newState == State.CONNECTED) listener.onStatus("Hold an arrow to drive")
    }
}

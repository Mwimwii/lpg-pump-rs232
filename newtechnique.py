import serial
import threading
import time

# --- Configuration ---
COM_PORT = 'COM7'
BAUD_RATE = 9600
DATA_BITS = serial.EIGHTBITS
PARITY = serial.PARITY_NONE
STOP_BITS = serial.STOPBITS_ONE
SERIAL_READ_TIMEOUT =2 
SERIAL_WRITE_TIMEOUT = 10

# SET THIS TO True or False to test with/without hardware flow control
# Your C# application does not use hardware flow control (Handshake=None), it only asserts the RTS line high.
# To make this Python script behave the same way, RTSCTS must be False.
# This is the most likely fix for communication issues.
SERIAL_RTSCTS = False

# --- Global serial port object and control flag ---
ser = None
keep_running = True
raw_data_log = []

# --- Data Reception Handler (runs in a separate thread) ---
def serial_reader_thread():
    global ser, keep_running, raw_data_log
    print(f"[{time.strftime('%H:%M:%S')}] [ReaderThread] Started. Listening (RTSCTS={SERIAL_RTSCTS})...")
    last_heartbeat_time = time.time()
    heartbeat_interval = 5  # Print a heartbeat every 5 seconds if no data

    while keep_running:
        data_received_this_cycle = False
        if ser and ser.is_open:
            try:
                byte_read = ser.read(1) 
                if byte_read:
                    data_received_this_cycle = True
                    raw_data_log.append(byte_read)
                    hex_representation = byte_read.hex()
                    try:
                        char_representation = byte_read.decode('ascii', errors='replace')
                    except:
                        char_representation = '?' # Should not happen with replace
                    print(f"[{time.strftime('%H:%M:%S')}] [ReaderThread] RX Byte: 0x{hex_representation} ('{char_representation}')")
                    last_heartbeat_time = time.time() # Reset heartbeat timer on data
                    
                    if ser.in_waiting > 0:
                        remaining_bytes = ser.read(ser.in_waiting)
                        if remaining_bytes:
                            raw_data_log.append(remaining_bytes)
                            print(f"[{time.strftime('%H:%M:%S')}] [ReaderThread] RX Burst: {remaining_bytes.hex()} (ASCII: {remaining_bytes.decode('ascii', errors='replace')})")
            except serial.SerialTimeoutException:
                # This is expected if ser.read(1) times out (SERIAL_READ_TIMEOUT)
                pass 
            except serial.SerialException as e:
                print(f"[{time.strftime('%H:%M:%S')}] [ReaderThread] SerialException: {e}")
                time.sleep(0.5) # Avoid busy loop on error
                last_heartbeat_time = time.time() # Reset heartbeat timer
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] [ReaderThread] Unexpected error: {e}")
                time.sleep(0.5)
                last_heartbeat_time = time.time() # Reset heartbeat timer
        else:
            if not keep_running: # If main thread signaled stop
                break
            time.sleep(0.1) # Wait for port to open or keep_running to change

        # Heartbeat message if no data received in the interval
        current_time = time.time()
        if not data_received_this_cycle and (current_time - last_heartbeat_time > heartbeat_interval):
            print(f"[{time.strftime('%H:%M:%S')}] [ReaderThread] ...listening on {COM_PORT} (no data received recently)...")
            last_heartbeat_time = current_time
            
        time.sleep(0.01) # Main loop sleep for the reader thread

    print(f"[{time.strftime('%H:%M:%S')}] [ReaderThread] Stopped.")

# --- Function to send a command ---
def send_command_with_terminations(command_base_str):
    global ser
    if not (ser and ser.is_open):
        print(f"[{time.strftime('%H:%M:%S')}] [MainThread  ] Serial port not open. Cannot send '{command_base_str}'.")
        return

    # For focused testing, let's stick to one or two common terminations first.
    # The C# code does not explicitly add terminators, suggesting they might not be needed
    # or are part of the command string itself (like the '*' at the end).
    terminations = [""] # Send command as is (matching C# behavior)
    # terminations = ["", "\r\n"] # Test as-is and with CRLF

    for term in terminations:
        full_command = command_base_str + term
        try:
            print('Written 0')
            ser.write(full_command.encode('ascii'))
            print('Written 1')
            term_name = term.replace('\r', 'CR').replace('\n', 'LF') if term else "None"
            print(f"[{time.strftime('%H:%M:%S')}] [MainThread  ] Sent: '{command_base_str}' with termination: '{term_name}' (Bytes: {full_command.encode('ascii').hex()})")
            time.sleep(0.5) # Give a brief moment for the command to be processed
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] [MainThread  ] Error sending '{full_command}': {e}")
    # print(f"[{time.strftime('%H:%M:%S')}] [MainThread  ] Finished sending variants of '{command_base_str}'.") # Reduce verbosity

# --- Main Application Logic ---
if __name__ == "__main__":
    print(f"--- PayGas Python Serial Test (v4 - RTSCTS: {SERIAL_RTSCTS}) ---")
    print(f"[{time.strftime('%H:%M:%S')}] Attempting to connect to {COM_PORT} at {BAUD_RATE} baud.")

    try:
        ser = serial.Serial(
            port=COM_PORT,
            baudrate=BAUD_RATE,
            bytesize=DATA_BITS,
            parity=PARITY,
            stopbits=STOP_BITS,
            timeout=SERIAL_READ_TIMEOUT, # For ser.read()
            write_timeout=SERIAL_WRITE_TIMEOUT,
            rtscts=SERIAL_RTSCTS 
        )
        ser.dtr = True 
        ser.rts = True 

        if ser.is_open:
            print(f"[{time.strftime('%H:%M:%S')}] [MainThread  ] Serial port {ser.name} opened successfully (DTR={ser.dtr}, RTS={ser.rts}, RTSCTS={ser.rtscts}).")
            reader = threading.Thread(target=serial_reader_thread, daemon=True)
            reader.start()
            time.sleep(0.5) # Let reader thread initialize

            print(f"\n[{time.strftime('%H:%M:%S')}] [MainThread  ] Sending '$1,1*'.")
            print(f"[{time.strftime('%H:%M:%S')}] [MainThread  ] ACTION: If required by device, perform physical action (e.g., 'connect cylinder') NOW.")
            send_command_with_terminations("$1,1*") 
            
            print(f"\n[{time.strftime('%H:%M:%S')}] [MainThread  ] Listening for 20 seconds for response to '$1,1'...")
            print(f"[{time.strftime('%H:%M:%S')}] [MainThread  ] (Reader thread will print '...listening...' periodically if no data is received)")
            time.sleep(2)

            # Example of sending a subsequent command if the first one seemed to work
            # You would typically only do this if you received an expected response from '^start*'
            # print(f"\n[{time.strftime('%H:%M:%S')}] [MainThread  ] Optionally sending '!03.50,10.00*'")
            # send_command_with_terminations("!03.50,10.00*")
            # time.sleep(10)


            print(f"\n[{time.strftime('%H:%M:%S')}] [MainThread  ] Test sequence finished. Final listen for 5s.")
            time.sleep(5)

        else:
            print(f"[{time.strftime('%H:%M:%S')}] [MainThread  ] Failed to open serial port {COM_PORT}.")

    except serial.SerialException as e:
        print(f"[{time.strftime('%H:%M:%S')}] [MainThread  ] SERIAL ERROR: {e}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] [MainThread  ] UNEXPECTED ERROR: {e}")
    finally:
        print(f"[{time.strftime('%H:%M:%S')}] [MainThread  ] Cleaning up...")
        keep_running = False
        if ser and ser.is_open:
            ser.close()
            print(f"[{time.strftime('%H:%M:%S')}] [MainThread  ] Serial port {COM_PORT} closed.")
        if 'reader' in locals() and reader.is_alive():
            reader.join(timeout=2) # Wait a bit for the thread to join
        print(f"--- Test Finished (v4 - RTSCTS: {SERIAL_RTSCTS}) ---")

        if raw_data_log:
            print("\n--- Summary of Raw Bytes Received ---")
            full_log_bytes = b''.join(raw_data_log)
            print(f"Total bytes received: {len(full_log_bytes)}")
            print(f"Hex: {full_log_bytes.hex()}")
            print(f"ASCII (errors replaced): {full_log_bytes.decode('ascii', errors='replace')}")
        else:
            print("\nNo raw bytes were logged by the reader thread.")

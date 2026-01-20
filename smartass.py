import serial
import time
import threading

# --- Configuration ---
# We will now allow changing the baud rate at runtime.
SERIAL_PORT = 'COM7'
BAUD_RATE = 9600  # Starting baud rate
SCALE_ID = '1'

# --- Global variable to control background threads ---
stop_threads = False

def monitor_handshake_status(ser):
    """Monitors and displays the status of the RS232 handshake lines."""
    # This function remains the same...
    print("[MONITOR] Handshake monitoring thread started.")
    while not stop_threads:
        try:
            if not ser or not ser.is_open: break
            status_str = (
                f"Handshake Status -> "
                f"CTS: {'ON' if ser.cts else 'OFF'} | "
                f"DSR: {'ON' if ser.dsr else 'OFF'} | "
                f"DCD: {'ON' if ser.cd else 'OFF'}"
            )
            print(f"\r{status_str}", end="")
        except (serial.SerialException, OSError):
            break
        except Exception as e:
            print(f"\n[MONITOR] An unexpected error occurred: {e}")
            break
        time.sleep(0.2)

def handle_raw_bytes(raw_bytes):
    """
    Handles decoding of received bytes, with robust error handling.
    This is the key change to fix the UnicodeDecodeError.
    """
    print("\n--- Handling Response ---")
    if not raw_bytes:
        print("[INFO] Received an empty response.")
        return

    # Print the raw bytes in hex format for debugging
    hex_representation = ' '.join(f'{b:02x}' for b in raw_bytes)
    print(f"[RAW HEX DATA] {hex_representation}")

    try:
        # Attempt to decode as ASCII, as per the protocol
        decoded_str = raw_bytes.decode('ascii').strip()
        print(f"[DECODED ASCII] '{decoded_str}'")
        # If successful, parse it
        parse_response_string(decoded_str)
    except UnicodeDecodeError as e:
        print(f"\n[DECODE ERROR] FAILED to decode response as ASCII. {e}")
        print("[HINT] This strongly suggests the BAUD RATE is incorrect.")
        print("[HINT] Try changing the baud rate from the main menu.")
        # Try decoding with another common encoding as a fallback
        try:
            fallback_str = raw_bytes.decode('latin-1').strip()
            print(f"[FALLBACK DECODE] As 'latin-1': '{fallback_str}'")
        except:
            pass # Ignore if fallback also fails

def parse_response_string(response_str):
    """Parses a successfully decoded string."""
    print("--- Parsing Decoded String ---")
    if not response_str.startswith('$') or not response_str.endswith('*'):
        print("[PARSE ERROR] Invalid format. Response must start with '$' and end with '*'.")
        return
    # ... (rest of the parsing logic is the same)
    clean_response = response_str.strip('$*')
    parts = clean_response.split(',')
    status_codes = {
        '10': "Idle", '11': "Idle (has data in memory)",
        '70': "Fill Complete", '71': "Fill Complete (has data in memory)",
    }
    try:
        print(f"  - Scale ID: {parts[0]}")
        print(f"  - Responding to Command: {parts[1]}")
        if len(parts) == 3:
            status_code = parts[2]
            status_desc = status_codes.get(status_code, "Unknown Status Code")
            print(f"  - Status Code: {status_code} ({status_desc})")
    except (IndexError, ValueError) as e:
        print(f"[PARSE ERROR] Could not parse the response parts. Error: {e}")
    print("--- End of Parse ---\n")


def send_command(ser, command_code):
    """Constructs and sends a command, then handles the raw byte response."""
    command_str = f"${SCALE_ID},{command_code}*"
    print(f"\n[SENDING] Sending command: '{command_str}' at {ser.baudrate} baud.")
    try:
        # Clear input buffer to ensure we're getting a fresh response
        ser.reset_input_buffer()
        ser.write(command_str.encode('ascii'))
        
        # Read until the expected stop character
        response_bytes = ser.read_until(b'*')
        
        if response_bytes:
            handle_raw_bytes(response_bytes)
            return True
        else:
            print("[TIMEOUT] No response received from the scale.")
            return False
    except serial.SerialException as e:
        print(f"\n[SERIAL ERROR] Could not write to port: {e}")
        return False

def main():
    """Main function to run the diagnostic tool."""
    global stop_threads, BAUD_RATE
    ser = None
    monitor_thread = None

    while True: # Main loop to allow re-opening port with new settings
        print("\n--- ADCENG Scale Diagnostic Tool v4 ---")
        print(f"Current Settings: Port={SERIAL_PORT}, Baud Rate={BAUD_RATE}")

        try:
            ser = serial.Serial(
                port=SERIAL_PORT, baudrate=BAUD_RATE, bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=2
            )
            print(f"[SUCCESS] Serial port '{SERIAL_PORT}' opened successfully.")

            stop_threads = False
            monitor_thread = threading.Thread(target=monitor_handshake_status, args=(ser,))
            monitor_thread.daemon = True
            monitor_thread.start()
            time.sleep(0.5)

            # --- Inner Menu Loop ---
            while True:
                print("\n--- Main Menu ---")
                print(f"  b: Change Baud Rate (current: {BAUD_RATE})")
                print("  p: Auto-Poll Mode (to test current settings)")
                print("  1: Send Single Status Check")
                print("  exit: Close the program")
                choice = input("Enter your choice: ").strip().lower()

                if choice == 'exit':
                    stop_threads = True
                    if ser and ser.is_open: ser.close()
                    if monitor_thread and monitor_thread.is_alive(): monitor_thread.join()
                    print("Program terminated.")
                    return # Exit the entire program

                elif choice == 'b':
                    new_baud = input("Enter new baud rate (e.g., 4800, 9600, 19200): ").strip()
                    if new_baud.isdigit():
                        BAUD_RATE = int(new_baud)
                        print(f"Baud rate set to {BAUD_RATE}. Port will be reopened.")
                        # Break inner loop to reopen port with new settings
                        stop_threads = True
                        if ser and ser.is_open: ser.close()
                        if monitor_thread and monitor_thread.is_alive(): monitor_thread.join()
                        break 
                    else:
                        print("[ERROR] Invalid baud rate.")

                elif choice == 'p':
                    # Auto-poll logic here
                    print("\n--- Starting Auto-Polling Mode ---")
                    print("Press Ctrl+C to stop polling.")
                    try:
                        while True:
                            send_command(ser, '1')
                            time.sleep(3)
                    except KeyboardInterrupt:
                        print("\n[INFO] Auto-polling stopped by user.")
                
                elif choice.isdigit():
                    send_command(ser, choice)
                
                else:
                    print("[ERROR] Invalid choice.")

        except serial.SerialException as e:
            print(f"\n[FATAL ERROR] Could not open port '{SERIAL_PORT}'. Details: {e}")
            retry = input("Press Enter to retry, or type 'exit' to quit: ").lower()
            if retry == 'exit':
                break
        
if __name__ == '__main__':
    main()

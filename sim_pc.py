import serial
import time

# Configure the serial connection (adjust COM port as needed)
SERIAL_PORT = "/dev/ttys004"  # Change to "COMx" on Windows
BAUD_RATE = 9600

# Define polling interval
POLL_INTERVAL = 2  # Poll every 2 seconds
RECONNECT_DELAY = 5  # Wait 5s before reconnecting

def connect_serial():
    """Try to establish a serial connection."""
    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud.")
            return ser
        except serial.SerialException as e:
            print(f"Serial connection failed: {e}. Retrying in {RECONNECT_DELAY}s...")
            time.sleep(RECONNECT_DELAY)

def send_command(ser, command):
    """Send a formatted command to the scale."""
    try:
        full_command = f"${command}*"
        ser.write(full_command.encode())
        print(f"Sent: {full_command}")
    except serial.SerialException as e:
        print(f"Write error: {e}")

def read_response(ser):
    """Read and return a response from the scale."""
    try:
        response = ser.readline().decode().strip()
        if response:
            print(f"Received: {response}")
        return response
    except serial.SerialException as e:
        print(f"Read error: {e}")
        return None

def parse_response(response):
    """Parse response into a dictionary."""
    if response.startswith("$") and response.endswith("*"):
        parts = response[1:-1].split(",")
        try:
            return {
                "Scale ID": parts[0],
                "Command": parts[1],
                "Spare": parts[2],
                "Operator ID": parts[3],
                "Initial Mass": parts[4],
                "Tare Mass": parts[5],
                "Fill Mass": parts[6],
                "Last Measurement": parts[7],
                "Fill Sequence": parts[8],
                "Status Code": int(parts[9])
            }
        except (IndexError, ValueError):
            print("Error parsing response.")
    return None

def main():
        # Open serial connection
    ser = connect_serial()  # Initial connection

    while True:
        try:
            # Send poll request (requesting status)
            send_command(ser, "1,0")  # Scale ID = 1, Command = 0 (status request)

            # Read and parse response
            response = read_response(ser)
            if response:
                data = parse_response(response)
                if data:
                    print(f"Parsed Data: {data}")

                    # Check if status is 70 (fill complete)
                    if data["Status Code"] == 70:
                        print("Fill complete! Requesting transaction data...")
                        send_command(ser, "1,1")  # Request transaction data

            # Wait for next polling cycle
            time.sleep(POLL_INTERVAL)

        except serial.SerialException:
            print("Connection lost! Attempting to reconnect...")
            ser.close()
            ser = connect_serial()  # Auto-reconnect

        except KeyboardInterrupt:
            print("\nPolling stopped by user.")
            ser.close()
            break

if __name__ == "__main__":
    main()

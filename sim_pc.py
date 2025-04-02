import serial
import time

# Configure the serial connection (adjust COM port as needed)
SERIAL_PORT = "/dev/ttys004"  # Change to "COMx" on Windows
BAUD_RATE = 9600

# Define polling interval
POLL_INTERVAL = 2  # Poll every 2 seconds

def send_command(ser, command):
    """Send a formatted command to the scale."""
    full_command = f"${command}*"
    ser.write(full_command.encode())
    print(f"Sent: {full_command}")

def read_response(ser):
    """Read the response from the scale."""
    response = ser.readline().decode().strip()
    if response:
        print(f"Received: {response}")
    return response

def parse_response(response):
    """Parse the response into fields."""
    if response.startswith("$") and response.endswith("*"):
        parts = response[1:-1].split(",")
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
    return None

def main():
    try:
        # Open serial connection
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud.")

        while True:
            # Send poll command (e.g., request status)
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

    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except KeyboardInterrupt:
        print("\nPolling stopped by user.")
    finally:
        ser.close()
        print("Serial connection closed.")

if __name__ == "__main__":
    main()

import serial
import time
import logging
import requests

# Configure the serial connection (adjust COM port as needed)
SERIAL_PORT = "/dev/ttys007"  # Change to "COMx" on Windows
BAUD_RATE = 9600

# Define polling interval
POLL_INTERVAL = 2  # Poll every 2 seconds
RECONNECT_DELAY = 5  # Wait 5s before reconnecting

API_URL = "http://localhost:3000/transactions"
LOG_FILE = "transactions.log"

# --- SETUP LOGGING ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def connect_serial():
    logging.info("Starting RS232 Polling Script...")

    """Try to establish a serial connection."""
    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud.")
            logging.info(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud.")
            return ser
        except serial.SerialException as e:
            print(f"Serial connection failed: {e}. Retrying in {RECONNECT_DELAY}s...")
            logging.error(f"Serial connection failed: {e}")
            time.sleep(RECONNECT_DELAY)

def send_command(ser, command):
    """Send a formatted command to the scale."""
    try:
        full_command = f"${command}*"
        ser.write(full_command.encode())
        print(f"Sent: {full_command}")
        logging.info(f"Sent command: {full_command}")
    except serial.SerialException as e:
        print(f"Write error: {e}")

def read_response(ser):
    """Read and return a response from the scale."""
    try:
        response = ser.readline().decode().strip()
        if response:
            print(f"Received: {response}")
            logging.info(f"Received response: {response}")
        return response
    except serial.SerialException as e:
        print(f"Read error: {e}")
        logging.error(f"Read error: {e}")
        return None

def parse_response(response):
    """Parse scale response into a structured dictionary."""
    if response.startswith("$") and response.endswith("*"):
        parts = response[1:-1].split(",")
        try:
            parsed_data = {
                "scaleId": int(parts[0]),
                "operatorId": int(parts[3]),
                "initialMass": float(parts[4]),
                "tareMass": float(parts[5]),
                "fillMass": float(parts[6]),
                "lastMeasurement": float(parts[7]),
                "fillSequence": int(parts[8]),
                "statusCode": int(parts[9]),
            }
            logging.info(f"Parsed Data: {parsed_data}")
            return parsed_data
        except (IndexError, ValueError):
            print("Error parsing response.")
            logging.info("Error parsing response.")
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
                    if data and data["statusCode"] == 70:
                        print("Fill complete! Requesting transaction data...")
                        response = requests.post(API_URL, json=data)
                        if response.status_code == 200:
                            print("Transaction complete! Saving to database...")
                            logging.info("Transaction successfully saved.")
                        else:
                            print(f"API Error: {response.status_code} - {response.text}")
                            logging.error(f"API Error: {response.status_code} - {response.text}")
                        send_command(ser, "1,1")  # Request transaction data

            # Wait for next polling cycle
            time.sleep(POLL_INTERVAL)

        except serial.SerialException:
            print("Connection lost! Attempting to reconnect...")
            logging.error("Connection lost! Attempting to reconnect...")
            ser.close()
            ser = connect_serial()  # Auto-reconnect
            logging.info("Reconnected to serial port.")

        except KeyboardInterrupt:
            print("\nPolling stopped by user.")
            logging.info("Polling stopped by user.")
            ser.close()
            break

if __name__ == "__main__":
    main()

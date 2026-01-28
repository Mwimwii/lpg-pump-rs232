import sys
import os
import serial
import time
import logging
import requests
# from math import nan # math.nan check was problematic; direct try-except for int conversion is better
import argparse  # For better command-line argument parsing
import configparser  # For reading config file
# BADAD725

# --- CONFIGURATION LOADING ---
config = configparser.ConfigParser()
# Ensure the script looks for config.ini in its own directory,
# especially when run as a packaged executable.
script_dir = os.path.dirname(os.path.abspath(sys.argv[0])) # sys.argv[0] is reliable
config_file_path = os.path.join(script_dir, 'config.ini')

if not os.path.exists(config_file_path):
    print(f"Error: Configuration file 'config.ini' not found in {script_dir}")
    # Create a default config.ini if it doesn't exist for easier setup.
    default_config_content = """
                            [Settings]
                            ApiUrl = http://localhost:3000/transactions
                            LogFile = transactions.log
                            PollInterval = 2
                            ReconnectDelay = 5
                            DefaultBaudRate = 9600

                            [SerialPorts]
                            # Default serial port base names if not overridden by command line
                            # For Unix, if your ports are like /dev/ttyS0, /dev/ttyS1, use UnixBase = /dev/ttyS
                            # If they are /dev/ttys000, /dev/ttys001, use UnixBase = /dev/ttys
                            UnixBase = /dev/ttys
                            WindowsBase = COM
                            """
    try:
        with open(config_file_path, 'w') as f_cfg:
            f_cfg.write(default_config_content)
        print(f"A default 'config.ini' has been created in {script_dir}. Please review and modify it if necessary.")
    except IOError as e:
        print(f"Could not create default config file: {e}")
try:
    config.read(config_file_path)
    API_URL = config.get('Settings', 'ApiUrl', fallback="https://lpg-dev.zambiancivilservant.workers.dev/api/transactions")
    LOG_FILE_NAME = config.get('Settings', 'LogFile', fallback="transactions.log")
    POLL_INTERVAL = config.getint('Settings', 'PollInterval', fallback=2)
    RECONNECT_DELAY = config.getint('Settings', 'ReconnectDelay', fallback=5)
    DEFAULT_BAUD_RATE = config.getint('Settings', 'DefaultBaudRate', fallback=9600)
    SERIAL_PORT_UNIX_BASE = config.get('SerialPorts', 'UnixBase', fallback='/dev/ttys')
    SERIAL_PORT_WINDOWS_BASE = config.get('SerialPorts', 'WindowsBase', fallback='COM')
except Exception as e: # Catch broader exceptions during config load
    print(f"Error loading configuration from 'config.ini': {e}. Using hardcoded default values.")
    API_URL = "https://lpg-dev.zambiancivilservant.workers.dev/api/transactions"
    LOG_FILE_NAME = "transactions.log"
    POLL_INTERVAL = 2
    RECONNECT_DELAY = 5
    DEFAULT_BAUD_RATE = 9600
    SERIAL_PORT_UNIX_BASE = '/dev/ttys'
    SERIAL_PORT_WINDOWS_BASE = 'COM'


LOG_FILE = os.path.join(script_dir, LOG_FILE_NAME)  # Ensure log file is also relative to script dir

# --- SETUP LOGGING ---
# Ensure the directory for the log file exists
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# -- end region --

class SystemDriver():
    def __init__(self, log_file='error.log'):
        self.logging = logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

class AdcengDriver():
    def __init__(self,port, baud_rate=9600, reconnect_delay=5, poll_interval=2, log_file='transactions.log'):
        self.status_codes = {
            10: "Ready",
            11: "Ready (Data Pending Upload)",
            20: "Enter Tare Weight",
            21: "Enter Tare Weight (Data Pending Upload)",
            30: "Tare Error",
            31: "Tare Error (Data Pending Upload)",
            40: "Enter Fill Weight",
            41: "Enter Fill Weight (Data Pending Upload)",
            65: "Filling Cylinder...",
            51: "Filling Cylinder... (Data Pending Upload)",
            60: "Filling Error",
            61: "Filling Error (Data Pending Upload)",
            70: "Fill Complete - Remove Cylinder",
            71: "Fill Complete - Remove Cylinder (Data Pending Upload)",
        }
        self.baud_rate = baud_rate
        self.reconnect_delay= reconnect_delay
        self.poll_interval = poll_interval
        self.port = port
        self.logging = logging.getLogger(__name__) 
        # self.logging.basicConfig(
        #                     filename=log_file,
        #                     level=logging.INFO,
        #                     format="%(asctime)s | %(levelname)s | %(message)s",
        #                     datefmt="%Y-%m-%d %H:%M:%S",
        #                 )
        self.serial = self.connect_serial() # Initialize
        self.serial.dtr = True
        self.serial.rts = True

    def get_status(self, code):
        """Gets a user-friendly status string for a given ADCENG status code."""
        if code is None:
            return "Status Unknown"

        base_code = code
        if code in [11, 21, 31, 41, 51, 61, 65]: # Explicit check for pending codes
            base_code = code - 1

        status_text = self.status_codes.get(code, f"Unknown Status (Code: {code})") 
        
        return status_text

    def connect_serial(self): # Added baud_rate parameter
        self.logging.info(f"Attempting to connect to {self.port} at {self.baud_rate} baud...")
        while True:
            try:
                # Assign directly to the instance variable
                self.serial = serial.Serial(self.port, self.baud_rate, timeout=1)
                print(f"Connected to {self.port} at {self.baud_rate} baud.")
                return self.serial
            except serial.SerialException as e:
                print(f"Serial connection to {self.port} failed: {e}. Retrying in {self.reconnect_delay}s...")
                self.logging.error(f"Serial connection to {self.port} failed: {e}")
                time.sleep(self.reconnect_delay)

    def send_command(self, command):
        """Send a formatted command to the scale."""
        try:
            full_command = f"${command}*"
            # full_command = f"${command}*"
            self.serial.write(full_command.encode('ascii'))
            print(f"Sent: {full_command}")
            self.logging.info(f"Sent command: {full_command}")
        except serial.SerialException as e:
            print(f"Write error: {e}")
            self.logging.error(f"Write error: {e}") # Added logging for write error

    def read_response(self):
        """Read and return a response from the scale."""
        response_data = None # Initialize
        try:
            response_data = self.serial.readline().decode('ascii', errors='replace').strip()
            if response_data:
                print(f"Received: {response_data}")
                self.logging.info(f"Received response: {response_data}")
            return response_data
        except serial.SerialException as e:
            print(f"Read error: {e}")
            self.logging.error(f"Read error: {e}")
            return None
        except UnicodeDecodeError as e:
            print(f"Unicode decode error during read: {e}. Data: {response_data if response_data is not None else 'N/A'}")
            self.logging.error(f"Unicode decode error during read: {e}. Data: {response_data if response_data is not None else 'N/A'}")
            return None

    def parse_response(self, response):
        """Parse scale response into a structured dictionary."""
        if response and response.startswith("$") and response.endswith("*"): # Added check for non-empty response
            parts = response[1:-1].split(",")
            try:
                # Check if this is a short status response (e.g., $1,1,41,6*)
                if len(parts) < 10:
                    # Handle short responses - these appear to be status/acknowledgment messages
                    parsed_data = {
                        "scaleId": int(parts[0]) if len(parts) > 0 else None,
                        "commandCode": int(parts[1]) if len(parts) > 1 else None,
                        "statusCode": int(parts[2]) if len(parts) > 2 else None,
                        "checksum": int(parts[3]) if len(parts) > 3 else None,
                        "shortResponse": True,
                        "rawResponse": response
                    }
                    logging.info(f"Parsed short response: {parsed_data}")
                    return parsed_data
                else:
                    # Full response with all fields
                    parsed_data = {
                        "scaleId": int(parts[0]),
                        "operatorId": int(parts[3]),
                        "initialMass": float(parts[4]),
                        "tareMass": float(parts[5]),
                        "fillMass": float(parts[6]),
                        "lastMeasurement": float(parts[7]),
                        "fillSequence": int(parts[8]),
                        "statusCode": int(parts[9]),
                        "shortResponse": False,
                        "rawResponse": response
                    }
                    logging.info(f"Parsed Data: {parsed_data}")
                    return parsed_data
            except (IndexError, ValueError) as e:
                print(f"Error parsing response: {response}. Error: {e}")
                logging.error(f"Error parsing response: {response}. Error: {e}")
        return None

def run(ser_port_name, baud_rate): # Accept port name and baud rate
    adceng_driver = AdcengDriver(ser_port_name, baud_rate, RECONNECT_DELAY, POLL_INTERVAL, LOG_FILE)
    while True:
        try:
            # Send poll request (requesting status)
            adceng_driver.send_command("1,1")  # Scale ID = 1, Command = 0 (status request)

            # Read and parse response
            response_str = adceng_driver.read_response() # Renamed to avoid conflict
            if response_str:
                data = adceng_driver.parse_response(response_str)
                if data:
                    status_message = adceng_driver.get_status(data["statusCode"])
                    print(f"Parsed Data: {data} - Status: {status_message}") # Print status message

                    # Logic to send data to API:
                    logging.info(f"Attempting to send data to API: {API_URL}. Data: {data}")
                    try:
                        api_response = requests.post(API_URL, json=data, timeout=10) # Added timeout
                        if api_response.status_code == 200 or api_response.status_code == 201: # Check for 201 Created
                            print(f"Transaction data successfully sent to API. Status: {api_response.status_code}")
                            logging.info(f"Transaction successfully sent/saved to API. Response: {api_response.text}")
                            if data["statusCode"] % 10 != 0 : # If it was a "pending" status
                                print("Data was pending, attempting to clear status on scale...")
                                adceng_driver.send_command("1,1") # Command to confirm/clear transaction data from scale
                        else:
                            print(f"API Error: {api_response.status_code} - {api_response.text}")
                            logging.error(f"API Error: {api_response.status_code} - {api_response.text}")
                            # If API fails, do not send command "1,1" as data is not yet offloaded.
                    except requests.exceptions.RequestException as e:
                        print(f"Could not connect to API: {e}")
                        logging.error(f"Could not connect to API at {API_URL}: {e}")
                        # Don't send "1,1" if API connection failed.

            # Wait for next polling cycle
            time.sleep(POLL_INTERVAL)

        except serial.SerialException:
            print(f"Connection to {ser_port_name} lost! Attempting to reconnect...")
            logging.error(f"Connection to {ser_port_name} lost! Attempting to reconnect...")
            if ser and ser.is_open:
                ser.close()
            ser = adceng_driver.connect_serial()  # Auto-reconnect with original port and baud
            logging.info(f"Reconnected to serial port {ser_port_name}.")
        except requests.exceptions.ConnectionError as e:
            print(f"API connection error: {e}. Check if the server at {API_URL} is running. Retrying after delay...")
            logging.error(f"API connection error: {e}. Server: {API_URL}")
            time.sleep(RECONNECT_DELAY) # Wait before next loop iteration which will retry API
        except KeyboardInterrupt:
            print("\nPolling stopped by user.")
            logging.info("Polling stopped by user.")
            if ser and ser.is_open:
                ser.close()
            break
        except Exception as e: # Generic catch for other unexpected errors
            print(f"An unexpected error occurred: {e}")
            logging.exception("An unexpected error occurred in run loop") # Use logging.exception to include stack trace
            time.sleep(RECONNECT_DELAY)


def main():
    parser = argparse.ArgumentParser(description="Cleanergy LPG Script for Scales.")
    parser.add_argument("--port", required=True,
                        help="Serial port name (e.g., COM3, /dev/ttyS0, or just a number like 3 for COM3 or 003 for /dev/ttys003 depending on OS and config).")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE,
                        help=f"Baud rate for serial communication (default: {DEFAULT_BAUD_RATE} from config or {DEFAULT_BAUD_RATE if 'DEFAULT_BAUD_RATE' in globals() else 9600}).")

    args = parser.parse_args()

    target_port = args.port
    # If port is just a number, construct full name based on OS and config
    # This allows users to type "3" for COM3 or "001" for /dev/ttys001
    if args.port.isdigit():
        if sys.platform == "win32":
            target_port = f"{SERIAL_PORT_WINDOWS_BASE}{args.port}"
        else:  # Assuming Unix-like
            # If UnixBase is /dev/ttys and user types 1, it becomes /dev/ttys1
            # If UnixBase is /dev/ttyS and user types 0, it becomes /dev/ttyS0
            port_suffix = args.port # No zfill by default unless UnixBase expects it
            # Example: if SERIAL_PORT_UNIX_BASE is "/dev/ttys00" and user types "1", target_port = "/dev/ttys001"
            target_port = f"{SERIAL_PORT_UNIX_BASE}{port_suffix}"
    
    print(f"Starting Cleanergy LPG Script for port: {target_port} at {args.baud} baud.")
    logging.info(f"Script started. Target Port: {target_port}, Baud Rate: {args.baud}")
    # run(target_port, args.baud)
    
    adceng_driver = AdcengDriver(target_port, args.baud, RECONNECT_DELAY, POLL_INTERVAL, LOG_FILE)
    adceng_driver.send_command("1,1")  # Scale ID = 1, Command = 0 (status request)
    response_str = adceng_driver.read_response() 
    print(response_str)

if __name__ == "__main__":
    main()
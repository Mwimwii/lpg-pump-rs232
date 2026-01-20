import serial
import time

# --- Configuration ---
PORT = 'COM7'
BAUDRATE = 9600
# Set a timeout to detect when the device is not responding.
READ_TIMEOUT = 2  # seconds
POLL_INTERVAL = 3 # seconds

# --- Commands ---
# We encode the commands here to bytes for sending.
CMD_START = b'^start*'
CMD_ABORT = b'^abort*'
# Per your request, the poll command omits the Scale ID.
CMD_POLL_STATUS = b'$,1*'

# --- Setup Serial Port ---
# Configure the port directly in the constructor for clarity.
# We will open it inside the try block.
ser = serial.Serial()
ser.port = PORT
ser.baudrate = BAUDRATE
ser.timeout = READ_TIMEOUT
# DTR/RTS are often not needed for simple protocols, setting to False
# can sometimes resolve connection issues. Change if your device requires them.
ser.dtr = False
ser.rts = False

def initiate_connection():
    """Sends the start command to the device."""
    print(f"--> Sending initial command: {CMD_START.decode()}")
    ser.write(CMD_START)
    time.sleep(1) # Give the device a moment to process the command.

def reset_connection():
    """Sends abort, then start, to reset the communication sequence."""
    print("--- No response received, attempting to reset connection... ---")
    print(f"--> Sending abort command: {CMD_ABORT.decode()}")
    ser.write(CMD_ABORT)
    time.sleep(1)
    initiate_connection()

# --- Main Application Logic ---
try:
    print(f"Opening serial port {PORT}...")
    ser.open()
    
    initiate_connection()

    while True:
        print(f"--> Polling for status with: {CMD_POLL_STATUS.decode()}")
        ser.write(CMD_POLL_STATUS)
        
        # ser.readline() will wait for data until the timeout is reached.
        response = ser.readline()

        # Check if the response is empty (timeout occurred).
        if not response:
            reset_connection()
        else:
            # If we got data, decode and print it.
            decoded_response = response.decode('ascii', errors='replace').strip()
            print(f"<-- Received: {decoded_response}")

        # Wait before the next poll.
        print(f"--- Waiting for {POLL_INTERVAL} seconds... ---")
        time.sleep(POLL_INTERVAL)

except KeyboardInterrupt:
    print("\nProgram stopped by user.")
except serial.SerialException as e:
    print(f"Serial Error: {e}. Please check the connection and port name.")
finally:
    if ser.is_open:
        print("Closing serial port.")
        ser.close()

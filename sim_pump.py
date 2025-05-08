import sys
from math import nan
import serial

# -- region constants and init --
SERIAL_PORT_UNIX = '/dev/ttys'  # Change to "COMx" on Windows
SERIAL_PORT_WINDOWS = 'COM'
BAUD_RATE = 9600
POLL_INTERVAL = 2  # Poll every 2 seconds

# -- end region --

def start_pump(ser):
    while True:
        data = ser.readline().decode().strip()
        if data.startswith("$"):
            print(f"Received: {data}")

            # Simulate response based on command
            response = "$2,2,0,1,810,500,900,1402,32,70*"  # Example response
            ser.write(response.encode())
            print(f"Sent: {response}")

try:
    if(int(sys.argv[1]) is nan):
        raise ValueError(sys.argv[1], 'is not a port number')
    port = (SERIAL_PORT_WINDOWS if sys.platform == "win32" else SERIAL_PORT_UNIX) + str(sys.argv[1])
    ser = serial.Serial(port, BAUD_RATE, timeout=2)  # Adjust COM port
    start_pump(ser)
except IndexError as e:
    print('You must provide the serial pair (001, 002, 003) for UNIX based systems or (1, 2, 3) for Windows com ports\npython sim_pc.py 007')

import serial

# Open the virtual COM port
ser = serial.Serial('/dev/ttys005', 9600, timeout=2)  # Adjust COM port

while True:
    data = ser.readline().decode().strip()
    if data.startswith("$"):
        print(f"Received: {data}")
        
        # Simulate response based on command
        response = "$2,2,0,1,810,500,900,1402,32,70*"  # Example response
        ser.write(response.encode())
        print(f"Sent: {response}")


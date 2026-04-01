# Cleanergy LPG Pump Interface & Simulation System

## Overview

This project provides an interface for ADCENG LPG filling scales via RS232 serial communication. It includes:

1. A consolidated Python backend (`backend.py`) that handles serial communication, background polling, and SQLite logging via a REST API.
2. A Python script (`sim_pump.py`) to simulate an ADCENG LPG scale for development and testing.
3. A .NET tester (`csharp/PayGasConsoleTester.csproj`) to test the communication protocol.

## Features

* Communicates with ADCENG LPG scales using the Adceng Communications Protocol
* Background polling with automatic transaction logging to SQLite
* REST API for status queries, fill commands, and transaction history
* Simulates ADCENG scale responses for offline development
* Configurable serial port settings for Windows and Unix systems
* Auto-reconnect on serial connection loss

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run with serial port (e.g., COM10 on Windows, /dev/ttys10 on Unix)
python backend.py --port 10 --api-port 8000

# Or with full path
python backend.py --port /dev/ttys10
```

The API will be available at `http://localhost:8000` with automatic Swagger docs at `/docs`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Current pump status (on-demand poll) |
| POST | `/start-fill` | Initiate a fill operation |
| GET | `/transactions` | List all transactions |
| POST | `/transactions` | Create transaction manually |
| GET | `/transactions/{id}` | Get specific transaction |
| GET | `/polling/status` | Check if background polling is running |
| POST | `/polling/start` | Start background polling |
| POST | `/polling/stop` | Stop background polling |
| GET | `/health` | Health check |

## Architecture

**Single Python backend (`backend.py`)** combines:
- **AdcengDriver**: Serial communication with ADCENG protocol
- **Background Polling**: Polls pump every 2 seconds, saves transactions on activity
- **SQLite Database**: Local storage (`lpg_transactions.db`)
- **FastAPI Server**: REST API on port 8000

## Technology Stack

* **Python 3.x** with FastAPI, SQLAlchemy, pyserial
* **SQLite** for local transaction storage
* **(Windows simulation)** com0com for virtual serial ports
* **.NET** for the protocol tester

## Prerequisites

1. **Python 3.8+** with pip
2. **Python packages**: `pip install -r requirements.txt`
3. **(Windows simulation only)** com0com for virtual serial ports

## Configuration

**`config.ini`** controls runtime settings:
```ini
[Settings]
LogFile = transactions.log
PollInterval = 2
ReconnectDelay = 5
DefaultBaudRate = 9600

[SerialPorts]
UnixBase = /dev/ttys
WindowsBase = COM
```

**Environment variables:**
- `SERIAL_PORT`: Serial port path (required)
- `SERIAL_BAUD`: Baud rate override (optional, default 9600)

## Running in Simulation Mode (Windows)

1. Install com0com and create a virtual port pair (e.g., `COM10` <=> `COM11`)
2. Start the pump simulator on one port:
   ```bash
   # Edit sim_pump.py to use COM11
   python sim_pump.py
   ```
3. Start the backend on the other port:
   ```bash
   python backend.py --port 10
   ```

**Note on com0com:** Modern Windows may require disabling Secure Boot for unsigned drivers.

## Running with Real Hardware

1. Connect the ADCENG scale via RS232 (USB adapter)
2. Find the COM port in Device Manager
3. Run:
   ```bash
   python backend.py --port 3  # For COM3
   ```

## .NET Protocol Tester

```bash
cd csharp
dotnet build
dotnet run
```

## Logging

- **Console**: All activity logged to stdout
- **File**: Logged to `transactions.log`
- **Database**: Transactions saved to `lpg_transactions.db`

## ADCENG Protocol Reference

- Baud: 9600, Data: 8 bits, Parity: None, Stop: 1
- Packet format: `$<data>,<data>*`
- Status codes:
  - 10/11: Ready
  - 20/21: Enter Tare Weight
  - 30/31: Tare Error
  - 40/41: Enter Fill Weight
  - 50/51/65: Filling
  - 60/61: Filling Error
  - 70/71: Fill Complete

Odd codes indicate data pending upload.

## Troubleshooting

* Check `transactions.log` for errors
* Verify COM port is correct and not in use
* Confirm serial settings match (9600, 8N1)
* For Windows simulation, ensure com0com drivers are active
* Use `/health` endpoint to check connection status

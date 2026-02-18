# backend.py
# Consolidated FastAPI backend for LPG pump control
# Combines serial communication, background polling, and SQLite logging
#
# Run with:
#   python backend.py --port 10 --host 0.0.0.0 --api-port 8000
# Or with uvicorn:
#   SERIAL_PORT=COM7 uvicorn backend:app --reload --host 0.0.0.0 --port 8000
# Connect to host computer with id 285428038

import os
import sys
import asyncio
import logging
import configparser
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

import serial
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
import uvicorn
import argparse

# --- CONFIGURATION LOADING ---
script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
config_file_path = os.path.join(script_dir, 'config.ini')

config = configparser.ConfigParser()
if os.path.exists(config_file_path):
    config.read(config_file_path)

# Load from config.ini with fallbacks
POLL_INTERVAL = config.getint('Settings', 'PollInterval', fallback=2)
RECONNECT_DELAY = config.getint('Settings', 'ReconnectDelay', fallback=5)
DEFAULT_BAUD_RATE = config.getint('Settings', 'DefaultBaudRate', fallback=9600)
LOG_FILE_NAME = config.get('Settings', 'LogFile', fallback='transactions.log')
SERIAL_PORT_UNIX_BASE = config.get('SerialPorts', 'UnixBase', fallback='/dev/ttys')
SERIAL_PORT_WINDOWS_BASE = config.get('SerialPorts', 'WindowsBase', fallback='COM')

# Database path
DATABASE_PATH = os.path.join(script_dir, 'lpg_transactions.db')
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Log file path
LOG_FILE = os.path.join(script_dir, LOG_FILE_NAME)

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- DATABASE SETUP ---
Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scale_id = Column(Integer, nullable=False)
    operator_id = Column(Integer, nullable=False)
    initial_mass = Column(Float, nullable=False)
    tare_mass = Column(Float, nullable=False)
    fill_mass = Column(Float, nullable=False)
    last_measurement = Column(Float, nullable=False)
    fill_sequence = Column(Integer, nullable=False)
    status_code = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

# --- PYDANTIC MODELS ---


class FillRequest(BaseModel):
    current_weight: float
    fill_weight: float


class TransactionCreate(BaseModel):
    scale_id: int
    operator_id: int
    initial_mass: float
    tare_mass: float
    fill_mass: float
    last_measurement: float
    fill_sequence: int
    status_code: int


class TransactionResponse(BaseModel):
    id: int
    scale_id: int
    operator_id: int
    initial_mass: float
    tare_mass: float
    fill_mass: float
    last_measurement: float
    fill_sequence: int
    status_code: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- ADCENG DRIVER ---
class AdcengDriver:
    # Base status codes (divisible by 8) - from ADCENG COMMS.txt
    # Lower 3 bits are flags:
    #   bit0 (+1): EEPROM data pending (use cmd 4 to read, cmd 5 to ack)
    #   bit1 (+2): Current transaction data available (use cmd 2 to read, cmd 3 to ack)
    BASE_STATUS_CODES = {
        8: "Idle",
        16: "Tare Entered",
        24: "Tare Error",
        32: "Fill Entered",
        40: "Pumping",
        48: "Fill Error",
        56: "Fill Complete",
        64: "Zeroing",
    }

    @staticmethod
    def decode_status(code: int) -> tuple:
        """Decode status code into base status and flags.
        Returns: (base_status, has_eeprom_data, has_current_data)
        """
        if code is None:
            return (None, False, False)
        base_status = code & 0xF8  # Strip lower 3 bits
        has_eeprom_data = bool(code & 0x01)  # bit0
        has_current_data = bool(code & 0x02)  # bit1
        return (base_status, has_eeprom_data, has_current_data)

    def __init__(self, port: str, baud_rate: int = 9600):
        self.port = port
        self.baud_rate = baud_rate
        self.serial: Optional[serial.Serial] = None
        self._connect()

    def _connect(self):
        """Establish serial connection."""
        try:
            self.serial = serial.Serial(self.port, self.baud_rate, timeout=1)
            self.serial.dtr = True
            self.serial.rts = True
            logger.info(f"Connected to {self.port} at {self.baud_rate} baud")
        except serial.SerialException as e:
            logger.error(f"Failed to connect to {self.port}: {e}")
            raise

    def reconnect(self):
        """Attempt to reconnect to serial port."""
        if self.serial and self.serial.is_open:
            self.serial.close()
        self._connect()

    def is_connected(self) -> bool:
        return self.serial is not None and self.serial.is_open

    def get_status_text(self, code: Optional[int]) -> str:
        """Get human-readable status text from status code."""
        if code is None:
            return "Status Unknown"

        base_status, has_eeprom, has_current = self.decode_status(code)
        base_text = self.BASE_STATUS_CODES.get(base_status, f"Unknown Base Status ({base_status})")

        flags = []
        if has_eeprom:
            flags.append("EEPROM data pending")
        if has_current:
            flags.append("Current data available")

        if flags:
            return f"{base_text} [{', '.join(flags)}]"
        return base_text

    def send_command(self, command: str):
        """Send a formatted command to the scale."""
        if not self.is_connected():
            raise serial.SerialException("Serial port not connected")
        full_command = f"${command}*"
        self.serial.write(full_command.encode('ascii'))
        logger.debug(f"Sent: {full_command}")

    def read_response(self) -> Optional[str]:
        """Read response from the scale."""
        if not self.is_connected():
            return None
        try:
            response = self.serial.readline().decode('ascii', errors='replace').strip()
            if response:
                logger.debug(f"Received: {response}")
            return response if response else None
        except (serial.SerialException, UnicodeDecodeError) as e:
            logger.error(f"Read error: {e}")
            return None

    def parse_response(self, response: str) -> Optional[dict]:
        """Parse scale response into a structured dictionary.

        Short response format: $scale_id,cmd,status[,progress]*
        - During pumping (status 40), 4th field is progress (1-10)

        Full response format: $scale_id,cmd,?,operator_id,initial,tare,fill,last,seq,status*
        - Mass values are raw integers, divide by 100 to get kg
        """
        if not response or not response.startswith("$") or not response.endswith("*"):
            return None

        parts = response[1:-1].split(",")
        try:
            if len(parts) < 10:
                # Short status response
                status_code = int(parts[2]) if len(parts) > 2 else None
                base_status, _, _ = self.decode_status(status_code)

                result = {
                    "scale_id": int(parts[0]) if len(parts) > 0 else None,
                    "command_code": int(parts[1]) if len(parts) > 1 else None,
                    "status_code": status_code,
                    "short_response": True,
                    "raw_response": response
                }

                # During pumping (base status 40), 4th field is progress indicator (1-10)
                if base_status == 40 and len(parts) > 3:
                    result["progress"] = int(parts[3])
                elif len(parts) > 3:
                    result["checksum"] = int(parts[3])

                return result
            else:
                # Full response with transaction data
                # Mass values are transmitted as integers (e.g., 1000 = 10.00 kg)
                return {
                    "scale_id": int(parts[0]),
                    "operator_id": int(parts[3]),
                    "initial_mass": float(parts[4]) / 100.0,
                    "tare_mass": float(parts[5]) / 100.0,
                    "fill_mass": float(parts[6]) / 100.0,
                    "last_measurement": float(parts[7]) / 100.0,
                    "fill_sequence": int(parts[8]),
                    "status_code": int(parts[9]),
                    "short_response": False,
                    "raw_response": response
                }
        except (IndexError, ValueError) as e:
            logger.error(f"Error parsing response '{response}': {e}")
            return None

    def close(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("Serial port closed")


# --- GLOBAL STATE ---
driver: Optional[AdcengDriver] = None
polling_task: Optional[asyncio.Task] = None
polling_enabled = True


# --- BACKGROUND POLLING ---
async def poll_loop(scale_id: str = "1"):
    """Background task that continuously polls the pump and logs transactions.

    Status code bit flags (from ADCENG COMMS.txt):
    - bit0 (+1): EEPROM data pending - use command 4 to read, command 5 to ack
    - bit1 (+2): Current transaction data available - use command 2 to read, command 3 to ack
    """
    global driver, polling_enabled

    last_status_code = None
    last_fill_sequence = None

    while polling_enabled:
        try:
            if not driver or not driver.is_connected():
                logger.warning("Driver not connected, skipping poll cycle")
                await asyncio.sleep(RECONNECT_DELAY)
                if driver:
                    try:
                        driver.reconnect()
                    except Exception as e:
                        logger.error(f"Reconnection failed: {e}")
                continue

            # Poll for status (command 1)
            driver.send_command(f"{scale_id},1")
            await asyncio.sleep(0.3)
            response = driver.read_response()

            if response:
                data = driver.parse_response(response)
                if data:
                    status_code = data.get("status_code")
                    status_text = driver.get_status_text(status_code)

                    # Decode status flags
                    base_status, has_eeprom_data, has_current_data = driver.decode_status(status_code)

                    # Log status changes
                    if status_code != last_status_code:
                        logger.info(f"Status changed: {status_text} (Code: {status_code}, Base: {base_status})")
                        last_status_code = status_code

                    # Log progress during pumping
                    if base_status == 40 and "progress" in data:
                        logger.info(f"Pumping progress: {data['progress']}/10")

                    # Handle bit1: Current transaction data available (command 2/3)
                    if has_current_data:
                        logger.info("Current transaction data available (bit1 set), requesting with command 2...")
                        await asyncio.sleep(0.2)
                        driver.send_command(f"{scale_id},2")
                        await asyncio.sleep(0.3)
                        full_response = driver.read_response()
                        if full_response:
                            full_data = driver.parse_response(full_response)
                            if full_data and not full_data.get("short_response"):
                                logger.info(f"Received current transaction: {full_response}")
                                fill_sequence = full_data.get("fill_sequence")
                                if fill_sequence != last_fill_sequence:
                                    save_transaction(full_data)
                                    last_fill_sequence = fill_sequence
                                    logger.info(f"Transaction saved: fill_sequence={fill_sequence}")
                                # Acknowledge receipt (command 3)
                                logger.info("Acknowledging current transaction (command 3)...")
                                driver.send_command(f"{scale_id},3")
                                await asyncio.sleep(0.2)
                                driver.read_response()  # Read ack response

                    # Handle bit0: EEPROM data pending (command 4/5) - catch-up mode
                    if has_eeprom_data and not has_current_data:
                        logger.info("EEPROM data pending (bit0 set), requesting with command 4...")
                        await asyncio.sleep(0.2)
                        driver.send_command(f"{scale_id},4")
                        await asyncio.sleep(0.3)
                        eeprom_response = driver.read_response()
                        if eeprom_response:
                            eeprom_data = driver.parse_response(eeprom_response)
                            if eeprom_data and not eeprom_data.get("short_response"):
                                logger.info(f"Received EEPROM transaction: {eeprom_response}")
                                fill_sequence = eeprom_data.get("fill_sequence")
                                if fill_sequence != last_fill_sequence:
                                    save_transaction(eeprom_data)
                                    last_fill_sequence = fill_sequence
                                    logger.info(f"EEPROM transaction saved: fill_sequence={fill_sequence}")
                                # Acknowledge EEPROM data (command 5)
                                logger.info("Acknowledging EEPROM data (command 5)...")
                                driver.send_command(f"{scale_id},5")
                                await asyncio.sleep(0.2)
                                driver.read_response()  # Read ack response

                    # If we got full data in the initial response, save it
                    if not data.get("short_response"):
                        fill_sequence = data.get("fill_sequence")
                        if fill_sequence != last_fill_sequence and fill_sequence is not None:
                            save_transaction(data)
                            last_fill_sequence = fill_sequence
                            logger.info(f"Transaction saved from poll: fill_sequence={fill_sequence}")

        except serial.SerialException as e:
            logger.error(f"Serial error during polling: {e}")
            await asyncio.sleep(RECONNECT_DELAY)
        except Exception as e:
            logger.exception(f"Unexpected error during polling: {e}")
            await asyncio.sleep(RECONNECT_DELAY)

        await asyncio.sleep(POLL_INTERVAL)


def save_transaction(data: dict):
    """Save transaction data to SQLite database."""
    session = SessionLocal()
    try:
        transaction = Transaction(
            scale_id=data["scale_id"],
            operator_id=data["operator_id"],
            initial_mass=data["initial_mass"],
            tare_mass=data["tare_mass"],
            fill_mass=data["fill_mass"],
            last_measurement=data["last_measurement"],
            fill_sequence=data["fill_sequence"],
            status_code=data["status_code"]
        )
        session.add(transaction)
        session.commit()
        logger.info(f"Saved transaction ID: {transaction.id}")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to save transaction: {e}")
    finally:
        session.close()


# --- FASTAPI APP ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global driver, polling_task, polling_enabled

    serial_port = os.environ.get("SERIAL_PORT")
    if not serial_port:
        logger.error(
            "SERIAL_PORT not set. Set via environment variable or .env file.\n"
            "Example: SERIAL_PORT=COM7 or SERIAL_PORT=/dev/ttys010"
        )
        raise RuntimeError("SERIAL_PORT environment variable is required")

    serial_baud = int(os.environ.get("SERIAL_BAUD", str(DEFAULT_BAUD_RATE)))

    logger.info(f"Connecting to {serial_port} at {serial_baud} baud...")

    try:
        driver = AdcengDriver(serial_port, serial_baud)
    except Exception as e:
        logger.error(f"Failed to initialize driver: {e}")
        raise

    # Start background polling
    polling_enabled = True
    polling_task = asyncio.create_task(poll_loop())
    logger.info("Background polling started")

    yield

    # Shutdown
    polling_enabled = False
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    if driver:
        driver.close()
    logger.info("Shutdown complete")


app = FastAPI(
    lifespan=lifespan,
    title="LPG Pump Backend",
    description="Consolidated backend for ADCENG LPG pump control with background polling and SQLite logging"
)


# --- API ENDPOINTS ---
@app.get("/status")
def get_status():
    """Get current pump status (on-demand poll)."""
    global driver
    if not driver or not driver.is_connected():
        raise HTTPException(status_code=500, detail="Serial port not connected")

    driver.send_command("1,1")
    import time
    time.sleep(0.3)
    raw = driver.read_response()
    parsed = driver.parse_response(raw) if raw else None

    if parsed:
        parsed["status_text"] = driver.get_status_text(parsed.get("status_code"))
        return parsed

    return {"raw_response": raw or "No response", "parsed": False}


@app.post("/start-fill")
def start_fill(request: FillRequest):
    """Initiate a fill operation."""
    global driver
    if not driver or not driver.is_connected():
        raise HTTPException(status_code=500, detail="Serial port not connected")

    import time

    # Send start command
    start_cmd = "^start*"
    driver.serial.write(start_cmd.encode("ascii"))
    logger.info(f"Sent: {start_cmd}")

    # Wait for pump acknowledgment
    max_retries = 10
    pump_ready = False
    raw_response = ""

    for _ in range(max_retries):
        time.sleep(0.1)
        if driver.serial.in_waiting > 0:
            raw_response = driver.read_response()
            if raw_response and "$" in raw_response:
                pump_ready = True
                break

    if not pump_ready:
        raise HTTPException(
            status_code=504,
            detail=f"Pump did not respond to start command. Last received: {raw_response}"
        )

    # Send fill configuration
    fill_cmd = f"!{request.current_weight},{request.fill_weight}*"
    driver.serial.write(fill_cmd.encode("ascii"))
    logger.info(f"Sent: {fill_cmd}")

    return {
        "status": "Fill command sent",
        "init_response": raw_response,
        "config_sent": fill_cmd
    }


@app.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """List transactions from the database."""
    session = SessionLocal()
    try:
        transactions = session.query(Transaction).order_by(
            Transaction.created_at.desc()
        ).offset(offset).limit(limit).all()
        return transactions
    finally:
        session.close()


@app.get("/transactions/count")
def count_transactions():
    """Return total number of transactions."""
    session = SessionLocal()
    try:
        total = session.query(Transaction).count()
        return {"total": total}
    finally:
        session.close()


@app.post("/transactions", response_model=TransactionResponse)
def create_transaction(data: TransactionCreate):
    """Manually create a transaction record."""
    session = SessionLocal()
    try:
        transaction = Transaction(
            scale_id=data.scale_id,
            operator_id=data.operator_id,
            initial_mass=data.initial_mass,
            tare_mass=data.tare_mass,
            fill_mass=data.fill_mass,
            last_measurement=data.last_measurement,
            fill_sequence=data.fill_sequence,
            status_code=data.status_code
        )
        session.add(transaction)
        session.commit()
        session.refresh(transaction)
        return transaction
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: int):
    """Get a specific transaction by ID."""
    session = SessionLocal()
    try:
        transaction = session.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return transaction
    finally:
        session.close()


@app.post("/polling/start")
async def start_polling():
    """Start background polling (if stopped)."""
    global polling_task, polling_enabled
    if polling_task and not polling_task.done():
        return {"status": "Polling already running"}

    polling_enabled = True
    polling_task = asyncio.create_task(poll_loop())
    return {"status": "Polling started"}


@app.post("/polling/stop")
async def stop_polling():
    """Stop background polling."""
    global polling_task, polling_enabled
    polling_enabled = False
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    return {"status": "Polling stopped"}


@app.get("/polling/status")
def polling_status():
    """Check if background polling is running."""
    global polling_task, polling_enabled
    return {
        "enabled": polling_enabled,
        "running": polling_task is not None and not polling_task.done()
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    global driver
    return {
        "status": "ok",
        "serial_connected": driver.is_connected() if driver else False,
        "database": "sqlite",
        "database_path": DATABASE_PATH
    }


# --- STATIC FILE SERVING ---
FRONTEND_DIR = os.path.join(script_dir, "frontend", "dist")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/")
    def serve_index():
        """Serve the frontend index.html."""
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/{path:path}")
    def serve_spa(path: str):
        """Catch-all for SPA routing - serve index.html for non-API routes."""
        file_path = os.path.join(FRONTEND_DIR, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# --- CLI ENTRY POINT ---
def resolve_port(port_arg: str) -> str:
    """Resolve port argument to full port path."""
    if port_arg.isdigit():
        if sys.platform == "win32":
            return f"{SERIAL_PORT_WINDOWS_BASE}{port_arg}"
        else:
            return f"{SERIAL_PORT_UNIX_BASE}{port_arg}"
    return port_arg


def main():
    parser = argparse.ArgumentParser(description="LPG Pump Backend Server")
    parser.add_argument("--port", required=True,
                        help="Serial port (e.g., COM3, /dev/ttys10, or just a number)")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE,
                        help=f"Baud rate (default: {DEFAULT_BAUD_RATE})")
    parser.add_argument("--host", default="0.0.0.0",
                        help="API host to bind (default: 0.0.0.0)")
    parser.add_argument("--api-port", type=int, default=8000,
                        help="API port (default: 8000)")
    parser.add_argument("--reload", action="store_true",
                        help="Enable auto-reload (development)")

    args = parser.parse_args()

    # Set environment variables for the lifespan function
    serial_port = resolve_port(args.port)
    os.environ["SERIAL_PORT"] = serial_port
    os.environ["SERIAL_BAUD"] = str(args.baud)

    print(f"Starting LPG Pump Backend")
    print(f"  Serial: {serial_port} @ {args.baud} baud")
    print(f"  API: http://{args.host}:{args.api_port}")
    print(f"  Database: {DATABASE_PATH}")
    print(f"  Log file: {LOG_FILE}")
    print(f"  Poll interval: {POLL_INTERVAL}s")
    print()
    print("Endpoints:")
    print("  GET  /status          - Current pump status")
    print("  POST /start-fill      - Start a fill operation")
    print("  GET  /transactions    - List transactions")
    print("  POST /transactions    - Create transaction manually")
    print("  GET  /polling/status  - Check polling status")
    print("  POST /polling/start   - Start polling")
    print("  POST /polling/stop    - Stop polling")
    print("  GET  /health          - Health check")
    print()

    uvicorn.run(
        "backend:app",
        host=args.host,
        port=args.api_port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()

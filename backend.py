# backend.py
# FastAPI backend for LPG pump control using AdcengDriver
# Automatically loads .env file (if present) using python-dotenv
# .env example:
# SERIAL_PORT=COM7
# SERIAL_BAUD=9600
#
# Run with:
#   python backend.py --host 0.0.0.0 --port 8000 --reload
# Or:
#   uvicorn backend:app --reload --host 0.0.0.0 --port 8000

import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import argparse

# Load .env file automatically (safe to call even if no .env exists)
from dotenv import load_dotenv
load_dotenv()  # <-- This reads your .env file into os.environ

from sim_pc import AdcengDriver

SCALE_ID = "1"

driver = None  # Set per worker in lifespan


class FillRequest(BaseModel):
    current_weight: float
    fill_weight: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    global driver

    serial_port = os.environ.get("SERIAL_PORT")
    if not serial_port:
        raise RuntimeError(
            "ERROR: SERIAL_PORT is not set!\n"
            "Create a .env file in the project root with:\n"
            "SERIAL_PORT=COM7\n"
            "SERIAL_BAUD=9600\n"
            "(Adjust COM7 to your actual port)"
        )

    serial_baud = int(os.environ.get("SERIAL_BAUD", "9600"))

    print(f"Worker startup: Connecting to {serial_port} at {serial_baud} baud...")
    driver = AdcengDriver(serial_port, serial_baud)

    # Initial poll
    print("Performing initial status poll...")
    driver.send_command(f"{SCALE_ID},1")
    time.sleep(0.5)
    initial_resp = driver.read_response()
    if initial_resp:
        print(f"Configuration OK - initial response: {initial_resp}")
        parsed = driver.parse_response(initial_resp)
        status_text = driver.get_status(parsed.get("statusCode")) if parsed else "Parse failed (short/incomplete response)"
        print(f"Initial status: {status_text}")
    else:
        print("Warning: No response to initial poll - check wiring/power/serial settings")

    yield

    # Shutdown cleanup
    if driver and driver.serial and driver.serial.is_open:
        driver.serial.close()
        print("Serial port closed on worker shutdown")


app = FastAPI(lifespan=lifespan, title="LPG Pump Backend")


@app.get("/status")
def get_status():
    global driver
    if not driver or not driver.serial.is_open:
        raise HTTPException(status_code=500, detail="Serial port not connected")

    driver.send_command(f"{SCALE_ID},1")
    time.sleep(0.2)
    raw = driver.read_response()
    parsed = driver.parse_response(raw) if raw else None

    if parsed:
        parsed["status_text"] = driver.get_status(parsed.get("statusCode"))
        return parsed

    return {"raw_response": raw or "No response", "parsed": False, "note": "Short responses (like status-only) are common and will be improved in parse_response later"}


@app.post("/start-fill")
def start_fill(request: FillRequest):
    global driver
    if not driver or not driver.serial.is_open:
        raise HTTPException(status_code=500, detail="Serial port not connected")

    # STEP 1: Send Start Command FIRST 
    start_cmd = "^start*"
    driver.serial.write(start_cmd.encode("ascii"))
    print(f"Sent: {start_cmd}")

    # STEP 2: Listen for the '$' response 
    # We need to wait for the pump to ask for data. 
    # The C# code checks if the response starts with ASCII 36 ($).
    max_retries = 10
    pump_ready = False
    raw_response = ""
    
    for _ in range(max_retries):
        time.sleep(0.1)
        if driver.serial.in_waiting > 0:
            raw_response = driver.read_response() # Implement a read that reads until '*'
            # Check for the specific trigger character '$' (ASCII 36)
            if raw_response and "$" in raw_response:
                pump_ready = True
                break
    
    if not pump_ready:
        raise HTTPException(status_code=504, detail=f"Pump did not respond to start command. Last received: {raw_response}")

    # STEP 3: Send Fill Configuration 
    # Format: !CurrentWeight,FillWeight*
    fill_cmd = f"!{request.current_weight},{request.fill_weight}*"
    driver.serial.write(fill_cmd.encode("ascii"))
    print(f"Sent: {fill_cmd}")
    
    return {
        "status": "Command Sequence Sent",
        "init_response": raw_response,
        "config_sent": fill_cmd
    }
    
def main():
    parser = argparse.ArgumentParser(description="LPG Pump FastAPI Backend")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (development)")

    args = parser.parse_args()

    print("Starting server...")
    print(f"Loaded SERIAL_PORT={os.environ.get('SERIAL_PORT')}")
    print(f"Loaded SERIAL_BAUD={os.environ.get('SERIAL_BAUD', '9600 (default)')}")
    print(f"Server will run at http://{args.host}:{args.port}")
    print("Endpoints: GET /status  |  POST /start-fill")

    uvicorn.run("backend:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
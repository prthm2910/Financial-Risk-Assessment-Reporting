"""

This module defines the FastAPI backend service that powers the financial
risk analysis and ESG insight generation system. It exposes API endpoints
for triggering the agent pipeline and retrieving server logs.

Endpoints:
    - POST /run_agent: Trigger the multi-agent risk and ESG analysis for a given company.
    - GET /logs: Return in-memory logs of requests and events for the current day.

Features:
    - Asynchronous I/O for non-blocking agent execution
    - Thread-safe in-memory logging with daily rollover
    - CORS support for frontend integration (e.g., Streamlit, React)
"""

from fastapi import FastAPI
from agents.agent import run_agent
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from datetime import datetime, date
from threading import Lock
from pydantic import BaseModel
import time

app = FastAPI(
    title="InsightBestAI Risk API",
    description="API service for financial risk assessment and ESG insights using multi-agent architecture.",
    version="1.0.0"
)

# CORS Middleware: Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory log buffer for audit trail (rotated daily)
log_buffer = []
log_buffer_date = date.today()
log_lock = Lock()


class AgentRequest(BaseModel):
    """
    Schema for POST request to the /run_agent endpoint.

    Attributes:
        company_name (str): The name of the company to analyze.
    """
    company_name: str


@app.post("/run_agent")
async def call_agent(data: AgentRequest):
    """
    Runs the risk and ESG analysis for a given company using the AI agent pipeline.

    This endpoint is asynchronous and logs both the start and completion of the request.

    Args:
        data (AgentRequest): JSON body containing the company name.

    Returns:
        dict: Structured response containing financial risks, ESG report, and knowledge graph.
    """
    start_time = time.time()
    log_message(f"📥 Received request for company: {data.company_name}")
    
    response = await run_agent(data.company_name)
    
    end_time = time.time()
    elapsed = f"{end_time - start_time:.2f} seconds"
    log_message(f"✅ Completed request for {data.company_name} in {elapsed}")
    
    return response


def log_message(message: str):
    """
    Adds a timestamped message to the in-memory log buffer.

    Clears the log buffer if the current date has changed since last log entry.

    Args:
        message (str): Message to append to the log.
    """
    global log_buffer, log_buffer_date
    with log_lock:
        # Rotate log buffer daily
        if date.today() != log_buffer_date:
            log_buffer = []
            log_buffer_date = date.today()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_buffer.append(f"[{timestamp}] {message}")


@app.get("/logs", response_class=PlainTextResponse)
def get_logs():
    """
    Returns the current day's logs from memory.

    Returns:
        str: Newline-separated log entries.
    """
    with log_lock:
        return "\n".join(log_buffer)

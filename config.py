"""Central configuration for the Autonomous Finance Clerk."""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
MODEL_NAME = os.getenv("MODEL_NAME", "gemini/gemini-2.0-flash")

# Agent Behavior
MAX_STEPS = int(os.getenv("MAX_STEPS", "15"))
APPROVAL_THRESHOLD = float(os.getenv("APPROVAL_THRESHOLD", "1000.00"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Database
DB_PATH = os.path.join(os.path.dirname(__file__), "company_system", "company.db")

# Invoice Directory
INVOICE_DIR = os.path.join(os.path.dirname(__file__), "invoices")

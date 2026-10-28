
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).with_name(".env"))

app = FastAPI(title="PayPilot AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_methods=["GET"],
    allow_headers=["*"]
)


@app.get("/")
def home():
    return {"message": "Welcome to PayPilot AI!"}


@app.get("/api/health")
def health():
    return {"status": "online"}


@app.get("/api/paypal/check")
async def check_paypal():
    client_id = os.getenv("PAYPAL_CLIENT_ID")
    secret = os.getenv("PAYPAL_CLIENT_SECRET")

    if not client_id or not secret:
        return {
            "connected": False,
            "message": "Missing PayPal Sandbox credentials"
        }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api-m.sandbox.paypal.com/v1/oauth2/token",
                auth=httpx.BasicAuth(client_id, secret),
                data={"grant_type": "client_credentials"}
            )

        response.raise_for_status()

        token = response.json().get("access_token")

        return {
            "connected": bool(token),
            "message": (
                "PayPal Sandbox connected successfully!"
                if token else "Authentication failed."
            )
        }

    except (httpx.HTTPError, ValueError):
        return {
            "connected": False,
            "message": "PayPal connection failed."
        }

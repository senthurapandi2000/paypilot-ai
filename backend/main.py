
import secrets
from fastapi import Request
from fastapi.responses import JSONResponse
import uuid
import os
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit


import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

load_dotenv(Path(__file__).with_name(".env"))

PAYPAL_BASE = "https://api-m.sandbox.paypal.com"

app = FastAPI(
    title="PayPilot AI",
    description="AI-powered payment operations - Sandbox",
    version="0.2.0"
)


# Day 5 - Restricted sandbox demo access
@app.middleware("http")
async def require_demo_access(request: Request, call_next):
    path = request.url.path

    if path.startswith("/api/") and path != "/api/health":
        expected = os.getenv(
            "PAYPILOT_DEMO_KEY", ""
        ).strip()

        if not expected:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Demo access is not configured."
                }
            )

        provided = request.headers.get("X-Demo-Key", "")

        if not secrets.compare_digest(provided, expected):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Unauthorized demo request."
                }
            )

    return await call_next(request)



allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]

public_origin = os.getenv(
    "FRONTEND_ORIGIN", ""
).strip().rstrip("/")

if public_origin:
    allowed_origins.append(public_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=[
        "Content-Type",
        "Idempotency-Key",
        "X-Demo-Key"
    ]
)



class InvoiceInput(BaseModel):
    customer_email: EmailStr
    item_name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(ge=1, le=100)
    unit_price: Decimal = Field(
        gt=0,
        le=Decimal("999999.99"),
        decimal_places=2
    )


async def get_paypal_token(client: httpx.AsyncClient):
    client_id = os.getenv("PAYPAL_CLIENT_ID", "").strip()
    secret = os.getenv("PAYPAL_CLIENT_SECRET", "").strip()

    if not client_id or not secret:
        raise HTTPException(
            status_code=400,
            detail="Missing PayPal Sandbox credentials."
        )

    response = await client.post(
        f"{PAYPAL_BASE}/v1/oauth2/token",
        auth=httpx.BasicAuth(client_id, secret),
        data={"grant_type": "client_credentials"},
        headers={"Accept": "application/json"}
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="PayPal Sandbox authentication failed."
        )

    token = response.json().get("access_token")
    if not token:
        raise HTTPException(
            status_code=502,
            detail="PayPal did not return an access token."
        )

    return token


@app.get("/")
def home():
    return {"message": "Welcome to PayPilot AI!"}


@app.get("/api/health")
def health():
    return {"status": "online"}


@app.get("/api/demo/verify")
def verify_demo_access():
    return {
        "authorized": True,
        "message": "Sandbox demo access verified."
    }



@app.get("/api/paypal/check")
async def check_paypal():
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            await get_paypal_token(client)

        return {
            "connected": True,
            "message": "PayPal Sandbox connected successfully!"
        }

    except HTTPException as exc:
        return {"connected": False, "message": exc.detail}

    except (httpx.RequestError, ValueError):
        return {
            "connected": False,
            "message": "Unable to reach PayPal Sandbox."
        }


@app.post("/api/invoices/draft", status_code=201)

async def create_draft_invoice(
    data: InvoiceInput,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=16,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$"
    )
):
    request_id = idempotency_key or uuid.uuid4().hex

    price = data.unit_price.quantize(Decimal("0.01"))

    payload = {
        "detail": {
            "currency_code": "USD",
            "note": "PayPilot AI Sandbox demonstration.",
            "payment_term": {
                "term_type": "DUE_ON_RECEIPT"
            }
        },
        "invoicer": {
            "name": {
                "given_name": "PayPilot",
                "surname": "Demo"
            }
        },
        "primary_recipients": [
            {
                "billing_info": {
                    "email_address": str(data.customer_email)
                }
            }
        ],
        "items": [
            {
                "name": data.item_name,
                "quantity": str(data.quantity),
                "unit_amount": {
                    "currency_code": "USD",
                    "value": str(price)
                }
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token = await get_paypal_token(client)

            response = await client.post(
                f"{PAYPAL_BASE}/v2/invoicing/invoices",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "PayPal-Request-Id": request_id
                },
                json=payload
            )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Could not reach PayPal. Check your connection."
        )

    try:
        result = response.json()
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="PayPal returned an unreadable response."
        )

    if response.status_code != 201:
        error_name = result.get("name", "UNKNOWN_ERROR")

        if response.status_code in (401, 403):
            detail = (
                "PayPal denied invoice creation. "
                "Check Sandbox Business account and "
                "Invoicing API permissions."
            )
        else:
            issues = result.get("details") or []
            issue = (
                issues[0].get("issue", "")
                if isinstance(issues, list) and issues
                else ""
            )
            detail = f"PayPal error: {error_name}"
            if issue:
                detail += f" ({issue})"

        raise HTTPException(status_code=502, detail=detail)

    # PayPal can return an invoice link instead of an ID.
    
    invoice_id = result.get("id")

    if not invoice_id:
        urls = [
            result.get("href"),
            response.headers.get("Location")
        ]

        urls.extend(
            link.get("href")
            for link in result.get("links", [])
            if isinstance(link, dict)
        )

        for url in urls:
            if not isinstance(url, str):
                continue

            parts = urlsplit(url).path.split("/")

            for part in parts:
                if part.startswith("INV2-"):
                    invoice_id = part
                    break

            if invoice_id:
                break

    if not invoice_id:
        raise HTTPException(
            status_code=502,
            detail=(
                "PayPal accepted the request, but the "
                "invoice ID could not be extracted. "
                "Check the Sandbox invoice list before retrying."
            )
        )

    total = price * data.quantity

    return {
        "success": True,
        "invoice_id": invoice_id,
        "status": "DRAFT",
        "customer_email": str(data.customer_email),
        "item_name": data.item_name,
        "quantity": data.quantity,
        "unit_price": str(price),
        "total": str(total),
        "currency": "USD",
        "message": "Sandbox draft invoice created!"
    }


@app.get("/api/invoices/list")
async def list_invoices():
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token = await get_paypal_token(client)

            response = await client.get(
                f"{PAYPAL_BASE}/v2/invoicing/invoices",
                headers={
                    "Authorization": f"Bearer {token}"
                },
                params={
                    "page": 1,
                    "page_size": 30
                }
            )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Unable to connect to PayPal."
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve Sandbox invoices."
        )

    result = response.json()
    invoices = []

    for invoice in result.get("items") or []:
        detail = invoice.get("detail") or {}
        amount = invoice.get("amount") or {}

        invoices.append({
            "invoice_id": invoice.get("id"),
            "status": invoice.get("status"),
            "invoice_number": detail.get("invoice_number"),
            "amount": amount.get("value"),
            "currency": amount.get("currency_code")
        })

    return {
        "count": len(invoices),
        "invoices": invoices
    }


# Day 3 - AI invoice preparation and approval
from ai_agent import install_ai_routes

install_ai_routes(
    app,
    InvoiceInput,
    create_draft_invoice
)

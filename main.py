import time
import uuid
from collections import defaultdict

from fastapi import FastAPI, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

app = FastAPI()

EMAIL = "23f2003326@ds.study.iitm.ac.in"

TOTAL_ORDERS = 50
RATE_LIMIT = 18
WINDOW = 10

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

# ---------------- Rate Limiting ----------------

clients = defaultdict(list)

# ---------------- Idempotency ----------------

idempotency_store = {}

# ---------------- Fixed Orders ----------------

orders = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]


@app.middleware("http")
async def rate_limit(request: Request, call_next):

    client = request.headers.get("X-Client-Id", "anonymous")
    now = time.time()

    clients[client] = [
        t for t in clients[client]
        if now - t < WINDOW
    ]

    if len(clients[client]) >= RATE_LIMIT:

        response = JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
        )

        response.headers["Retry-After"] = "10"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "Retry-After"

        return response

    clients[client].append(now)

    response = await call_next(request)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Expose-Headers"] = "Retry-After"

    return response


# ---------------- Root ----------------

@app.get("/")
def root():
    return {"status": "ok"}


# ---------------- OPTIONS ----------------

@app.options("/{path:path}")
async def options(path: str):

    response = Response(status_code=204)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Expose-Headers"] = "Retry-After"

    return response


# ---------------- POST /orders ----------------

@app.post("/orders", status_code=201)
def create_order(idempotency_key: str = Header(..., alias="Idempotency-Key")):

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4())
    }

    idempotency_store[idempotency_key] = order

    return order


# ---------------- GET /orders ----------------

@app.get("/orders")
def list_orders(limit: int = 10, cursor: str | None = None):

    start = int(cursor) if cursor else 0

    items = orders[start:start + limit]

    next_cursor = None

    if start + limit < len(orders):
        next_cursor = str(start + limit)

    return {
        "items": items,
        "next_cursor": next_cursor
    }
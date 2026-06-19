import asyncio
import hashlib
import os
import time
from contextlib import asynccontextmanager

import asyncpg
import httpx
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "benchmark")
DB_USER = os.getenv("DB_USER", "benchmark")
DB_PASSWORD = os.getenv("DB_PASSWORD", "benchmark")


async def create_pool_with_retry(timeout: float = 30.0) -> asyncpg.Pool:
    """Create an asyncpg pool, retrying for ~timeout seconds if Postgres is not ready yet."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    last_err: Exception | None = None
    while loop.time() < deadline:
        try:
            return await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                min_size=2,
                max_size=10,
            )
        except (OSError, asyncpg.PostgresError) as err:
            last_err = err
            await asyncio.sleep(1.0)
    raise RuntimeError(f"Could not connect to Postgres within {timeout}s") from last_err


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool_with_retry(30.0)
    # One shared HTTP client reused across all /aggregate requests. A per-request
    # client (and the default 100-connection limit) churns connections under load
    # and drops calls; a shared, generously-pooled client keeps connections alive.
    app.state.http = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0),
        limits=httpx.Limits(max_connections=200, max_keepalive_connections=200),
    )
    try:
        yield
    finally:
        await app.state.http.aclose()
        await app.state.pool.close()


app = FastAPI(default_response_class=ORJSONResponse, lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/serialize")
async def serialize():
    return {"id": 123, "name": "John Doe", "email": "john@example.com"}


@app.get("/users/{id}")
async def get_user(id: int):
    row = await app.state.pool.fetchrow(
        "SELECT id, name, email, created_at FROM users WHERE id = $1", id
    )
    if row is None:
        return ORJSONResponse(status_code=404, content={"error": "not found"})
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "created_at": row["created_at"].isoformat(),
    }


def _chained_sha256(rounds: int) -> str:
    """Chained SHA-256 over the lab seed. CPU-bound; runs in a threadpool."""
    h = hashlib.sha256(b"backend-decision-lab").digest()
    for _ in range(rounds - 1):
        h = hashlib.sha256(h).digest()
    return h.hex()


@app.get("/cpu/{rounds}")
async def cpu(rounds: int):
    if rounds <= 0:
        return ORJSONResponse(status_code=404, content={"error": "not found"})
    rounds = min(rounds, 10000000)
    loop = asyncio.get_event_loop()
    digest = await loop.run_in_executor(None, _chained_sha256, rounds)
    return {"rounds": rounds, "hash": digest}


@app.get("/aggregate")
async def aggregate():
    upstream_url = os.environ["UPSTREAM_URL"]
    url = f"{upstream_url}/delay/0.05"
    client: httpx.AsyncClient = app.state.http

    async def fetch() -> bool:
        try:
            resp = await client.get(url)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    start = time.perf_counter()
    results = await asyncio.gather(*(fetch() for _ in range(10)))
    took_ms = int((time.perf_counter() - start) * 1000)

    succeeded = sum(1 for ok in results if ok)
    return {"requests": 10, "succeeded": succeeded, "took_ms": took_ms}

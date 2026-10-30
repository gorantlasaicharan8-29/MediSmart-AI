import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app


async def test():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/health/db")
        print("DB_HEALTH_STATUS:", r.status_code)
        print("DB_HEALTH_JSON:", r.json())

        


if __name__ == "__main__":
    asyncio.run(test())

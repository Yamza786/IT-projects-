import asyncio
import time

import httpx


URL = "http://127.0.0.1:8000/health"
INTERVAL = 10  # seconds
TIMEOUT = 5.0


async def check_once(client: httpx.AsyncClient) -> bool:
    try:
        response = await client.get(URL, timeout=TIMEOUT)
        ok = response.status_code == 200
        print(
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"{URL} -> {response.status_code} ok={ok}"
        )
        if response.status_code >= 400:
            print("  Response body:", (response.text or "")[:500])
        return ok
    except Exception as error:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} ERROR: {error}")
        return False


async def monitor() -> None:
    async with httpx.AsyncClient() as client:
        while True:
            await check_once(client)
            await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(monitor())
    except KeyboardInterrupt:
        print("Stopped by user")

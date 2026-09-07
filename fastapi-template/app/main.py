from fastapi import FastAPI

app = FastAPI(title="FastAPI Template", version="0.1.0")


@app.get("/")
async def root():
    return {"message": "FastAPI template is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ping")
async def ping():
    return {"ping": "pong"}

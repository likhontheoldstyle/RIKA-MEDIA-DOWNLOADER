from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/api/ping")
async def ping():
    return JSONResponse({"pong": True, "runtime": "ok"})

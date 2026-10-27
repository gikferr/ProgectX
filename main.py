import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from db import init_db
from routes import profile, events, polls, admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(events.router)
app.include_router(polls.router)
app.include_router(admin.router)

@app.get("/health")
async def health():
    return {"status": "ok"}

# ⬇️ ВОТ ЭТИ СТРОЧКИ ДОЛЖНЫ БЫТЬ В САМОМ КОНЦЕ ⬇️
if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
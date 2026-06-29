from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cm_shared.settings import get_base_settings
from main.app.api.v1.admin.eval import router as admin_eval_router
from main.app.api.v1.chat import router as chat_router
from main.app.api.v1.conversations import router as conversations_router

settings = get_base_settings()

app = FastAPI(title="Agent Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(admin_eval_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "agent-service"}

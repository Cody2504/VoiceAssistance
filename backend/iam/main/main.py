from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cm_shared.settings import get_base_settings
from main.api.auth import router as auth_router
from main.api.users import router as users_router

settings = get_base_settings()

app = FastAPI(title="IAM Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "iam"}

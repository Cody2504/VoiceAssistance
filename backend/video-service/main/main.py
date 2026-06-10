import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cm_shared.settings import get_base_settings
from main.api.edit import router as edit_router
from main.api.grounding import router as grounding_router
from main.api.indexes import router as indexes_router
from main.api.qa import router as qa_router
from main.api.highlights import router as highlights_router
from main.api.moderate import router as moderate_router
from main.api.recommend import router as recommend_router
from main.api.search import router as search_router
from main.api.sounds import router as sounds_router
from main.api.segments import router as segments_router
from main.api.videos import router as videos_router
from main.api.when import router as when_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
settings = get_base_settings()

app = FastAPI(title="Video Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos_router)
app.include_router(indexes_router)
app.include_router(grounding_router)
app.include_router(search_router)
app.include_router(segments_router)
app.include_router(recommend_router)
app.include_router(highlights_router)
app.include_router(moderate_router)
app.include_router(sounds_router)
app.include_router(qa_router)
app.include_router(edit_router)
app.include_router(when_router)


@app.on_event("startup")
def warm_models():
    """Eagerly load Lighthouse so the first /ground or /highlights request
    doesn't pay the cold-start cost of loading both DETR heads + the visual
    and audio encoders. Best-effort: in CPU-only dev images where the
    checkpoints aren't mounted we log a warning and keep going."""
    try:
        from main.services.lighthouse_service import get_lighthouse
        get_lighthouse()
    except Exception as exc:
        logging.getLogger(__name__).warning("lighthouse warm-up failed (ok in dev): %s", exc)


@app.get("/health")
def health():
    return {"status": "ok", "service": "video-service"}

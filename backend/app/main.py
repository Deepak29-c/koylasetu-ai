from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audit, auth, dashboard, documents, pq_replies, qa, reports, topics, users
from app.core.config import get_settings

app = FastAPI(
    title="KoylaSetu AI",
    description="Verified AI reporting & parliamentary-reply assistant for CMPDI / CIL",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(qa.router)
app.include_router(audit.router)
app.include_router(users.router)
app.include_router(reports.router)
app.include_router(pq_replies.router)
app.include_router(pq_replies.export_router)
app.include_router(topics.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    audit,
    auth,
    dashboard,
    documents,
    metrics,
    pq_replies,
    qa,
    report_drafts,
    reports,
    review,
    topics,
    users,
)
from app.core import errors
from app.core.config import get_settings

app = FastAPI(
    title="KoylaSetu AI",
    description="Verified AI reporting & parliamentary-reply assistant for CMPDI / CIL",
    version="0.1.0",
)

# First, so it ends up inside CORSMiddleware: an unhandled 500 still gets CORS headers and
# the browser shows the real error instead of "cannot reach the server" (#69).
errors.install(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Without this the browser cannot read the filename the export endpoint sets, and
    # every download is saved under whatever name the frontend guessed.
    expose_headers=["Content-Disposition"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(qa.router)
app.include_router(review.router)
app.include_router(audit.router)
app.include_router(users.router)
app.include_router(report_drafts.router)  # before /reports/{id} routes
app.include_router(reports.router)
app.include_router(pq_replies.router)
app.include_router(pq_replies.export_router)
app.include_router(topics.router)
app.include_router(dashboard.router)
app.include_router(metrics.router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}

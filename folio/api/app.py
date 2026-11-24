"""FastAPI app factory. Routers are pre-wired; each agent fills only its own router module."""
from fastapi import FastAPI

from folio.api.routers import ask, books, eval, galaxy, health, search


def create_app() -> FastAPI:
    app = FastAPI(title="Folio", version="0.1.0")
    app.include_router(health.router)                  # B0: /health, /metrics
    app.include_router(books.router, prefix="/books")  # B1
    app.include_router(search.router)                  # B1: /search
    app.include_router(ask.router)                     # B3a: /ask (SSE)
    app.include_router(eval.router, prefix="/eval")    # B2: /eval/runs
    app.include_router(galaxy.router)                  # B3b: /galaxy
    return app


app = create_app()

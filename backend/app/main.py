from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import ConflitoDeEstado, NaoEncontrado
from app.routers import catalogos, continuidade, dashboard, ia, perdas, unidades

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["X-Total-Count", "Content-Disposition"])

for r in (catalogos, dashboard, unidades, perdas, continuidade, ia):
    app.include_router(r.router)


@app.exception_handler(NaoEncontrado)
async def _404(_: Request, exc: NaoEncontrado):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ConflitoDeEstado)
async def _409(_: Request, exc: ConflitoDeEstado):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/api/health", tags=["infra"])
def health():
    return {"status": "ok", "data_source": settings.data_source}

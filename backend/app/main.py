from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.router import api_router
from app.core.database import async_engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await async_engine.dispose()


app = FastAPI(
    title="DrugCheck API",
    description=(
        "Сервис проверки лекарственных взаимодействий. "
        "Поддерживает российские торговые названия через ГРЛС + международную базу DrugBank."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "DrugCheck API"}


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Добавляем BearerAuth — позволяет вставить токен напрямую в Swagger
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            if isinstance(operation, dict) and "security" in operation:
                operation["security"].append({"BearerAuth": []})
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

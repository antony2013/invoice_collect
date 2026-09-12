from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import engine
from app.modules.audit_logs.router import router as audit_logs_router
from app.modules.auth.router import router as auth_router
from app.modules.clients.me import router as clients_me_router
from app.modules.clients.router import router as clients_router
from app.modules.invoices.files import router as invoice_files_router
from app.modules.invoices.router import router as invoices_router
from app.modules.organizations.router import router as organizations_router
from app.modules.reports.router import router as reports_router
from app.modules.staff.router import router as staff_router

logger = logging.getLogger(__name__)

UI_DIR = Path(__file__).resolve().parent / "ui"

UI_PAGES = frozenset(
    {
        "index",
        "login",
        "register",
        "dashboard",
        "invoices",
        "invoice-detail",
        "clients",
        "staff",
        "audit-logs",
        "organization",
        "client-dashboard",
        "client-invoices",
        "client-invoice-detail",
    }
)


def _serve_index() -> FileResponse:
    return FileResponse(UI_DIR / "index.xhtml", media_type="text/html")


def _redirect_to_ui() -> RedirectResponse:
    return RedirectResponse(url="/ui/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


def _serve_page(page_name: str) -> FileResponse:
    if not page_name.endswith(".xhtml"):
        raise HTTPException(status_code=404, detail="Page not found")
    stem = page_name[: -len(".xhtml")]
    if stem not in UI_PAGES:
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(UI_DIR / page_name, media_type="text/html")


def create_ui_router() -> APIRouter:
    router = APIRouter(tags=["ui"], include_in_schema=False)
    router.add_api_route("/", _redirect_to_ui, methods=["GET"])
    router.add_api_route("/ui", _serve_index, methods=["GET"])
    router.add_api_route("/ui/", _serve_index, methods=["GET"])
    router.add_api_route("/ui/{page_name}", _serve_page, methods=["GET"])
    return router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("%s starting in %s environment", settings.app_name, settings.environment)
    yield
    engine.dispose()
    logger.info("%s stopped", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def no_cache_static(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/ui/static/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        if settings.environment == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains",
            )
        return response

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> Response:
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail if isinstance(exc.detail, str) else "error"},
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> Response:
        logger.exception(
            "Unhandled error on %s %s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        if settings.debug:
            raise exc
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    @app.get("/health", tags=["system"], include_in_schema=False)
    def root_health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{settings.api_v1_prefix}/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name, "version": "0.1.0"}

    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(organizations_router, prefix=settings.api_v1_prefix)
    app.include_router(staff_router, prefix=settings.api_v1_prefix)
    app.include_router(clients_me_router, prefix=settings.api_v1_prefix)
    app.include_router(clients_router, prefix=settings.api_v1_prefix)
    app.include_router(invoices_router, prefix=settings.api_v1_prefix)
    app.include_router(invoice_files_router, prefix=settings.api_v1_prefix)
    app.include_router(audit_logs_router, prefix=settings.api_v1_prefix)
    app.include_router(reports_router, prefix=settings.api_v1_prefix)

    app.include_router(create_ui_router())
    app.mount("/ui/static", StaticFiles(directory=UI_DIR / "static"), name="ui-static")

    return app


app = create_app()

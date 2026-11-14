"""路由聚合：统一 /api 前缀（Nginx 反代时剥掉 /api）。"""
from fastapi import APIRouter

from src.routes.audit import router as audit_router
from src.routes.auth import router as auth_router
from src.routes.change_requests import router as change_requests_router
from src.routes.conflicts import router as conflicts_router
from src.routes.dependencies import router as dependencies_router
from src.routes.exports import router as exports_router
from src.routes.health import router as health_router
from src.routes.metrics import router as metrics_router
from src.routes.overview import router as overview_router
from src.routes.reports import router as reports_router
from src.routes.runs import router as runs_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(overview_router)
api_router.include_router(metrics_router)
api_router.include_router(dependencies_router)
api_router.include_router(reports_router)
api_router.include_router(conflicts_router)
api_router.include_router(change_requests_router)
api_router.include_router(runs_router)
api_router.include_router(exports_router)
api_router.include_router(audit_router)

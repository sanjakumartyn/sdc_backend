from django.urls import path
from django.views.generic import TemplateView
from ninja import NinjaAPI
from common.exception.global_exception import register_exception_handlers
from . import views

# Instantiate Django Ninja API with premium OpenAPI doc configurations
api = NinjaAPI(
    title="Sales Intelligence API",
    version="1.0.0",
    description="Modular and clean Repository-Service-Route Sales Intelligence Backend",
    urls_namespace="api",
)

# Register central global exception handlers
register_exception_handlers(api)

# Import modular API routers
from features.signals.routes import router as signals_router
from features.deals.routes import router as deals_router
from features.callAgents.routes import router as call_agents_router
from features.companydata.routes import router as companydata_router
from features.dashboard.routes import router as dashboard_router
from features.ocr.routes import router as ocr_router

# Register API routes with clear prefixing and tags for Swagger grouping
api.add_router("/ocr", ocr_router, tags=["OCR"])
api.add_router("", call_agents_router, tags=["Question"])
api.add_router("/signals", signals_router, tags=["Signals"])
api.add_router("/deals", deals_router, tags=["Deals"])
api.add_router("/companydata", companydata_router, tags=["Company Data"])


urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html')),
    path('api/history', views.history),
    path('api/chat', views.chat),
    path('api/details/<str:name>', views.company_details),
    path('api/', api.urls),
]

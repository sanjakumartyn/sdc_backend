from django.urls import path
from ninja import NinjaAPI
from common.exception.global_exception import register_exception_handlers

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

# Register API routes with clear prefixing and tags for Swagger grouping
api.add_router("", call_agents_router, tags=["Question"])
api.add_router("/signals", signals_router, tags=["Signals"])
api.add_router("/deals", deals_router, tags=["Deals"])
api.add_router("/companydata", companydata_router, tags=["Company Data"])


urlpatterns = [
    path('api/', api.urls),
]

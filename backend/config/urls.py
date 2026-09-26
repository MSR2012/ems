from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from shared_kernel.interfaces.api.health import HealthView
from shared_kernel.interfaces.api.metrics import MetricsView

api_v1 = [
    path("health", HealthView.as_view(), name="health"),
    path("ops/metrics", MetricsView.as_view(), name="ops-metrics"),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("", include("identity.interfaces.api.urls")),
    path("", include("gmail_integration.interfaces.api.urls")),
    path("", include("mailbox_context.interfaces.api.urls")),
    path("", include("email_intelligence.interfaces.api.urls")),
]

urlpatterns = [
    path("api/v1/", include(api_v1)),
]

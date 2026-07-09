from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("app.urls")),
    path("data-portal/<path:path>", serve, {"document_root": settings.BASE_DIR / "data-portal"}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

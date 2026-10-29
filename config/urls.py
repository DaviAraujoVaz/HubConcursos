from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

from catalogo.views import calendario

admin.site.site_header = "ConcursoHub"
admin.site.site_title = "ConcursoHub"
admin.site.index_title = "Seus concursos"

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/catalogo/concurso/", permanent=False)),
    path("admin/", admin.site.urls),
    path("calendario.ics", calendario, name="calendario"),
]

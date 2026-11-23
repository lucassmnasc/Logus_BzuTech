"""URL configuration for myproject project."""

from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

from meu_app import views


def tela(nome):
    return TemplateView.as_view(template_name=f"meu_app/{nome}.html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", tela("home"), name="home"),
    path("carregando/", tela("carregando"), name="carregando"),
    path("questionario/", tela("questionario"), name="questionario"),
    path("configurar/", views.configurar_page, name="configurar"),
    path("resultado/", views.resultado_page, name="resultado"),
    path("chat/", views.chat_page, name="chat"),
    path("relatorio/pdf/", views.relatorio_pdf, name="relatorio_pdf"),
    # APIs da LOGUS AI
    path("api/simular/", views.api_simular, name="api_simular"),
    path("api/analises-ia/", views.api_analises_ia, name="api_analises_ia"),
    path("api/chat/", views.api_chat, name="api_chat"),
    path("api/dispositivos/", views.api_dispositivos, name="api_dispositivos"),
]

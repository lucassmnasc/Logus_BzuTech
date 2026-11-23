from django.contrib import admin

from .models import MensagemChat, SimulacaoLead


@admin.register(SimulacaoLead)
class SimulacaoLeadAdmin(admin.ModelAdmin):
    list_display = (
        "empresa",
        "nome",
        "segmento",
        "qtd_dispositivos",
        "roi_12m_pct",
        "payback_meses",
        "criado_em",
    )
    search_fields = ("nome", "email", "empresa")
    list_filter = ("segmento", "coleta_atual")


@admin.register(MensagemChat)
class MensagemChatAdmin(admin.ModelAdmin):
    list_display = ("session_id", "papel", "modo_ia", "criado_em")
    list_filter = ("papel", "modo_ia")
    search_fields = ("session_id", "conteudo")

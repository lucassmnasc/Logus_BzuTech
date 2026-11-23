"""Views das páginas e APIs de simulação e chatbot com IA da Bzu Tech."""

from __future__ import annotations

import json
import uuid

from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import MensagemChat, SimulacaoLead
from .services.catalog import listar_dispositivos
from .services.chatbot import enriquecer_analises_com_ia, responder_chat
from .services.roi_engine import analisar_operacao


def _parse_json_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}


def _get_or_create_session_id(request: HttpRequest) -> str:
    if not request.session.session_key:
        try:
            request.session.create()
        except DatabaseError:
            return uuid.uuid4().hex[:16]
    return request.session.session_key or uuid.uuid4().hex[:16]


def chat_page(request: HttpRequest):
    """Página dedicada do Consultor de IA Bzu Tech."""
    simulacao_inicial = request.session.get("bzu_ultima_simulacao") or analisar_operacao({})
    return render(
        request,
        "meu_app/chat.html",
        {
            "simulacao_inicial_json": json.dumps(simulacao_inicial, ensure_ascii=False),
            "dispositivos": listar_dispositivos(),
        },
    )


def resultado_page(request: HttpRequest):
    """Tela de resultado com a última simulação da sessão (ou padrão calculado)."""
    simulacao = request.session.get("bzu_ultima_simulacao") or analisar_operacao(
        {"qtd_dispositivos": 80, "segmento": "industria", "coleta_atual": "planilha-manual"}
    )
    return render(
        request,
        "meu_app/resultado.html",
        {
            "simulacao": simulacao,
            "simulacao_json": json.dumps(simulacao, ensure_ascii=False),
        },
    )


@require_GET
def api_dispositivos(request: HttpRequest) -> JsonResponse:
    """Retorna o catálogo configurável de dispositivos IoT Bzu Tech."""
    return JsonResponse({"dispositivos": listar_dispositivos()})


@csrf_exempt
@require_POST
def api_simular(request: HttpRequest) -> JsonResponse:
    """
    Recebe dados da operação (questionário + configurar), calcula dispositivos sugeridos,
    Payback e ROI, enriquece a análise com IA (quando configurada) e salva na sessão/banco.
    """
    payload = _parse_json_body(request)
    simulacao = analisar_operacao(payload)
    simulacao["modo_ia"] = "local"
    simulacao = enriquecer_analises_com_ia(simulacao)

    try:
        request.session["bzu_ultima_simulacao"] = simulacao
        request.session["bzu_contexto_operacao"] = simulacao["parametros"]
    except DatabaseError:
        pass

    # Persiste no banco se as migrations já tiverem sido aplicadas
    try:
        SimulacaoLead.objects.create(
            nome=str(payload.get("nome", ""))[:150],
            email=str(payload.get("email", ""))[:254],
            empresa=str(payload.get("empresa", ""))[:150],
            telefone=str(payload.get("telefone", ""))[:40],
            segmento=simulacao["parametros"]["segmento"],
            coleta_atual=simulacao["parametros"]["coleta_atual"],
            qtd_dispositivos=simulacao["parametros"]["qtd_dispositivos"],
            endpoint_preferido=simulacao["parametros"]["endpoint_preferido"],
            economia_anual_brl=simulacao["financeiro"]["economia_anual_brl"],
            roi_12m_pct=simulacao["financeiro"]["roi_12m_pct"],
            payback_meses=simulacao["financeiro"]["payback_meses"],
            reducao_energia_pct=simulacao["financeiro"]["reducao_energia_pct"],
            resultado_json=simulacao,
        )
    except DatabaseError:
        pass

    return JsonResponse(simulacao)


@csrf_exempt
@require_POST
def api_chat(request: HttpRequest) -> JsonResponse:
    """
    Endpoint do chatbot com IA.
    Recebe: { "mensagem": "...", "contexto": {...}, "historico": [...] }
    Retorna: { "resposta": "...", "simulacao": {...}, "contexto": {...}, "modo_ia": "gemini"|"local" }
    """
    payload = _parse_json_body(request)
    mensagem = str(payload.get("mensagem", "")).strip()
    if not mensagem:
        return JsonResponse({"erro": "Envie uma mensagem válida."}, status=400)

    contexto_sessao = {}
    try:
        contexto_sessao = request.session.get("bzu_contexto_operacao") or {}
    except DatabaseError:
        pass

    contexto_req = payload.get("contexto") if isinstance(payload.get("contexto"), dict) else {}
    contexto_combinado = {**contexto_sessao, **contexto_req}
    historico = payload.get("historico") if isinstance(payload.get("historico"), list) else []

    resposta, simulacao, contexto_atualizado, modo_ia = responder_chat(
        mensagem=mensagem,
        contexto=contexto_combinado,
        historico=historico,
    )

    try:
        request.session["bzu_contexto_operacao"] = contexto_atualizado
        request.session["bzu_ultima_simulacao"] = simulacao
    except DatabaseError:
        pass

    # Salva histórico no SQLite se migrado
    try:
        sid = _get_or_create_session_id(request)
        MensagemChat.objects.create(session_id=sid, papel="user", conteudo=mensagem, modo_ia=modo_ia)
        MensagemChat.objects.create(session_id=sid, papel="assistant", conteudo=resposta, modo_ia=modo_ia)
    except DatabaseError:
        pass

    return JsonResponse(
        {
            "resposta": resposta,
            "simulacao": simulacao,
            "contexto": contexto_atualizado,
            "modo_ia": modo_ia,
        }
    )

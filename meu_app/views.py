"""Views das páginas e APIs da LOGUS AI (simulação, chat e relatório PDF)."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict

from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import MensagemChat, SimulacaoLead
from .services.catalog import FATOR_COLETA, MODOS_OPERACAO, SEGMENTOS, listar_dispositivos
from .services.chatbot import enriquecer_analises_com_ia, responder_chat
from .services.roi_engine import analisar_operacao

SESSAO_SIM = "bzu_ultima_simulacao"
SESSAO_CTX = "bzu_contexto_operacao"
SIM_PADRAO = {"qtd_dispositivos": 80, "segmento": "industria", "coleta_atual": "planilha-manual"}


def _parse_json_body(request: HttpRequest) -> Dict[str, Any]:
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
        return data if isinstance(data, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


def _salvar_sessao(request: HttpRequest, simulacao: Dict[str, Any], contexto: Dict[str, Any] | None = None) -> None:
    try:
        request.session[SESSAO_SIM] = simulacao
        request.session[SESSAO_CTX] = contexto if contexto is not None else simulacao["parametros"]
    except DatabaseError:
        pass


def _simulacao_sessao(request: HttpRequest) -> Dict[str, Any]:
    try:
        sim = request.session.get(SESSAO_SIM)
    except DatabaseError:
        sim = None
    return sim or analisar_operacao(SIM_PADRAO)


def _session_id(request: HttpRequest) -> str:
    if not request.session.session_key:
        try:
            request.session.create()
        except DatabaseError:
            return uuid.uuid4().hex[:16]
    return request.session.session_key or uuid.uuid4().hex[:16]


def _opcoes_formulario() -> Dict[str, Any]:
    return {
        "segmentos": [(k, v["rotulo"]) for k, v in SEGMENTOS.items()],
        "modos": [(k, v["rotulo"]) for k, v in MODOS_OPERACAO.items()],
        "coletas": [(k, v["rotulo"]) for k, v in FATOR_COLETA.items()],
    }


# ----------------------------------------------------------------- páginas


def configurar_page(request: HttpRequest):
    return render(request, "meu_app/configurar.html", _opcoes_formulario())


def chat_page(request: HttpRequest):
    try:
        sim = request.session.get(SESSAO_SIM)
    except DatabaseError:
        sim = None
    return render(
        request,
        "meu_app/chat.html",
        {
            "simulacao": sim,
            **_opcoes_formulario(),
        },
    )


def resultado_page(request: HttpRequest):
    sim = _simulacao_sessao(request)
    return render(
        request,
        "meu_app/resultado.html",
        {"simulacao": sim, "simulacao_json": json.dumps(sim, ensure_ascii=False)},
    )


# ----------------------------------------------------------------- APIs


@require_GET
def api_dispositivos(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"dispositivos": listar_dispositivos()})


@csrf_exempt
@require_POST
def api_simular(request: HttpRequest) -> JsonResponse:
    """
    Calcula a simulação (dispositivos, Payback, ROI) a partir dos dados da empresa.
    Resposta rápida e determinística; os textos com Gemini são buscados depois em /api/analises-ia/.
    """
    payload = _parse_json_body(request)
    simulacao = analisar_operacao(payload)
    simulacao["modo_ia"] = "local"
    _salvar_sessao(request, simulacao)

    p, f = simulacao["parametros"], simulacao["financeiro"]
    try:
        SimulacaoLead.objects.create(
            nome=p["responsavel"],
            email=p["email"],
            empresa=p["empresa"],
            telefone=p["telefone"],
            cidade=p["cidade"],
            segmento=p["segmento"],
            coleta_atual=p["coleta_atual"],
            modo_operacao=p["modo_operacao"],
            descricao_operacao=p["descricao_operacao"],
            qtd_dispositivos=p["qtd_dispositivos"],
            endpoint_preferido=p["endpoint_preferido"],
            economia_anual_brl=f["economia_anual_brl"],
            roi_12m_pct=f["roi_12m_pct"],
            payback_meses=f["payback_meses"],
            reducao_energia_pct=f["reducao_energia_pct"],
            resultado_json=simulacao,
        )
    except DatabaseError:
        pass

    return JsonResponse(simulacao)


@csrf_exempt
@require_POST
def api_analises_ia(request: HttpRequest) -> JsonResponse:
    """Enriquece (em segundo plano no front-end) os textos da análise com Gemini."""
    payload = _parse_json_body(request)
    params = payload.get("parametros") if isinstance(payload.get("parametros"), dict) else payload
    simulacao = enriquecer_analises_com_ia(analisar_operacao(params))
    simulacao.setdefault("modo_ia", "local")
    _salvar_sessao(request, simulacao)
    return JsonResponse({"analises": simulacao["analises"], "modo_ia": simulacao["modo_ia"]})


@csrf_exempt
@require_POST
def api_chat(request: HttpRequest) -> JsonResponse:
    """
    Recebe { mensagem, contexto, historico } e retorna
    { resposta, simulacao, contexto, modo_ia }.
    """
    payload = _parse_json_body(request)
    mensagem = str(payload.get("mensagem", "")).strip()[:4000]
    if not mensagem:
        return JsonResponse({"erro": "Envie uma mensagem válida."}, status=400)

    try:
        contexto_sessao = request.session.get(SESSAO_CTX) or {}
    except DatabaseError:
        contexto_sessao = {}
    contexto_req = payload.get("contexto") if isinstance(payload.get("contexto"), dict) else {}
    historico = payload.get("historico") if isinstance(payload.get("historico"), list) else []

    resposta, simulacao, contexto, modo_ia = responder_chat(
        mensagem=mensagem, contexto={**contexto_sessao, **contexto_req}, historico=historico
    )
    if simulacao is not None:
        _salvar_sessao(request, simulacao, contexto)
    else:
        try:
            request.session[SESSAO_CTX] = contexto
        except DatabaseError:
            pass

    try:
        sid = _session_id(request)
        MensagemChat.objects.bulk_create(
            [
                MensagemChat(session_id=sid, papel="user", conteudo=mensagem, modo_ia=modo_ia),
                MensagemChat(session_id=sid, papel="assistant", conteudo=resposta, modo_ia=modo_ia),
            ]
        )
    except DatabaseError:
        pass

    return JsonResponse({"resposta": resposta, "simulacao": simulacao, "contexto": contexto, "modo_ia": modo_ia})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def relatorio_pdf(request: HttpRequest) -> HttpResponse:
    """
    Baixa o relatório PDF.
    GET: usa a última simulação da sessão. POST: recebe { parametros, analises } do navegador.
    """
    from .services.pdf_report import gerar_pdf, nome_arquivo  # import tardio: só carrega ReportLab quando usado

    if request.method == "POST":
        payload = _parse_json_body(request)
        params = payload.get("parametros") if isinstance(payload.get("parametros"), dict) else {}
        simulacao = analisar_operacao(params) if params else _simulacao_sessao(request)
        analises = payload.get("analises")
        if isinstance(analises, dict):
            for chave in ("economia", "roi", "payback", "eficiencia"):
                if isinstance(analises.get(chave), str) and analises[chave].strip():
                    simulacao["analises"][chave] = analises[chave].strip()[:800]
    else:
        simulacao = _simulacao_sessao(request)

    resposta = HttpResponse(gerar_pdf(simulacao), content_type="application/pdf")
    resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo(simulacao)}"'
    return resposta

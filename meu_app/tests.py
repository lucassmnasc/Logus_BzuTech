import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from meu_app.services.chatbot import extrair_parametros_mensagem, responder_chat
from meu_app.services.roi_engine import analisar_operacao


class RoiEngineTests(TestCase):
    def test_analise_basica_autocentro(self):
        res = analisar_operacao(
            {
                "qtd_dispositivos": 40,
                "segmento": "autocentro",
                "coleta_atual": "planilha-manual",
                "custo_energia_mensal": 15000,
            }
        )
        self.assertEqual(res["parametros"]["qtd_dispositivos"], 40)
        self.assertEqual(res["parametros"]["segmento"], "autocentro")
        self.assertEqual(sum(d["quantidade"] for d in res["dispositivos_sugeridos"]), 40)
        self.assertGreater(res["financeiro"]["economia_anual_brl"], 0)
        self.assertGreater(res["financeiro"]["roi_12m_pct"], 0)
        self.assertGreater(res["financeiro"]["payback_meses"], 0)

    def test_endpoint_preferido_lidera_mix(self):
        res = analisar_operacao({"qtd_dispositivos": 100, "endpoint": "EP400"})
        codigos = {d["codigo"]: d["quantidade"] for d in res["dispositivos_sugeridos"]}
        self.assertIn("EP400", codigos)
        self.assertGreaterEqual(codigos["EP400"], 60)


class ChatbotServiceTests(TestCase):
    def test_extracao_parametros_linguagem_natural(self):
        ctx = extrair_parametros_mensagem(
            "Tenho um autocentro com 45 equipamentos, gasto R$ 18 mil de energia e usamos planilha manual"
        )
        self.assertEqual(ctx["segmento"], "autocentro")
        self.assertEqual(ctx["qtd_dispositivos"], 45)
        self.assertEqual(ctx["custo_energia_mensal"], 18000.0)
        self.assertEqual(ctx["coleta_atual"], "planilha-manual")

    def test_responder_chat_local(self):
        resposta, sim, ctx, modo = responder_chat(
            "Opero uma indústria com 80 máquinas e sofro com paradas. Qual o payback e ROI?"
        )
        self.assertIn("Payback", resposta)
        self.assertIn("ROI", resposta)
        self.assertEqual(sim["parametros"]["qtd_dispositivos"], 80)
        self.assertEqual(ctx["segmento"], "industria")
        self.assertIn(modo, ("local", "gemini"))


class ApiViewsTests(TestCase):
    def test_api_dispositivos(self):
        resp = self.client.get(reverse("api_dispositivos"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["dispositivos"]), 4)

    def test_api_simular(self):
        resp = self.client.post(
            reverse("api_simular"),
            data=json.dumps({"dispositivos": 50, "endpoint": "EP300", "coleta_atual": "nao-coletamos"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["parametros"]["qtd_dispositivos"], 50)
        self.assertIn("roi_12m", data["formatado"])

    def test_api_chat(self):
        resp = self.client.post(
            reverse("api_chat"),
            data=json.dumps({"mensagem": "Tenho 30 veículos na frota, quais dispositivos usar?"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("resposta", data)
        self.assertEqual(data["simulacao"]["parametros"]["qtd_dispositivos"], 30)

    def test_chat_inicia_zerado_e_saudacao_nao_preenche(self):
        page = self.client.get(reverse("chat"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "R$ 0")
        self.assertContains(page, "Nenhum dispositivo sugerido ainda")

        resp = self.client.post(
            reverse("api_chat"),
            data=json.dumps({"mensagem": "oi"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["simulacao"])

    def test_relatorio_pdf(self):
        resp = self.client.post(
            reverse("relatorio_pdf"),
            data=json.dumps({
                "parametros": {
                    "empresa": "AutoCenter Recife",
                    "segmento": "autocentro",
                    "modo_operacao": "dois-turnos",
                    "qtd_dispositivos": 40,
                }
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))


class LoginViewTests(TestCase):
    def test_home_exibe_opcoes_de_login(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Bzu Cloud")
        self.assertContains(resp, f'href="{reverse("login")}">Simulador Cloud</a>')

    def test_login_get_renderiza_template_e_css(self):
        resp = self.client.get(reverse("login"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "meu_app/css/Login.css")
        self.assertContains(resp, "Login Bzu Cloud")

    def test_login_post_autentica_por_email(self):
        User = get_user_model()
        User.objects.create_user(username="usuario", email="usuario@bzu.com", password="segredo123")
        resp = self.client.post(reverse("login"), {"email": "usuario@bzu.com", "senha": "segredo123"})
        self.assertRedirects(resp, reverse("home"))

    def test_login_post_invalido_exibe_erro(self):
        resp = self.client.post(reverse("login"), {"email": "naoexiste@bzu.com", "senha": "errada"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "E-mail ou senha inválidos.")

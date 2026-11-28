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
        self.assertEqual(resp.content.decode().count(f'href="{reverse("login")}">Iniciar simulação</a>'), 2)

    def test_iniciar_simulacao_leva_usuario_logado_ao_questionario(self):
        user = get_user_model().objects.create_user(
            username="maria", email="maria@bzu.com", password="SenhaForte123!"
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content.decode().count(f'href="{reverse("questionario")}">Iniciar simulação</a>'), 2
        )

    def test_login_get_renderiza_template_e_css(self):
        resp = self.client.get(reverse("login"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "meu_app/css/login.css")
        self.assertContains(resp, "Entrar")
        self.assertContains(resp, f'href="{reverse("conta")}">Criar conta</a>')
        self.assertContains(resp, 'name="email"')
        self.assertContains(resp, 'name="senha"')
        self.assertNotContains(resp, 'name="empresa"')

    def test_login_post_autentica_por_email(self):
        User = get_user_model()
        User.objects.create_user(username="usuario", email="usuario@bzu.com", password="segredo123")
        resp = self.client.post(reverse("login"), {"email": "usuario@bzu.com", "senha": "segredo123"})
        self.assertRedirects(resp, reverse("home"))

    def test_login_post_invalido_exibe_erro(self):
        resp = self.client.post(reverse("login"), {"email": "naoexiste@bzu.com", "senha": "errada"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "E-mail ou senha inválidos.")

    def test_conta_get_exibe_campos_e_estilos(self):
        response = self.client.get(reverse("conta"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "meu_app/css/conta.css")
        for field in ("nome", "email", "empresa", "senha", "confirmar_senha"):
            self.assertContains(response, f'name="{field}"')

    def test_cadastro_cria_usuario_e_salva_dados_da_conta(self):
        resp = self.client.post(
            reverse("conta"),
            {
                "nome": "Maria Silva",
                "email": "nova@bzu.com",
                "empresa": "Bzu Tech",
                "senha": "SenhaForte123!",
                "confirmar_senha": "SenhaForte123!",
            },
        )
        self.assertRedirects(resp, reverse("home"))

        user = get_user_model().objects.get(email="nova@bzu.com")
        dados_conta = user.dados_conta
        self.assertEqual(user.first_name, "Maria Silva")
        self.assertEqual(dados_conta.nome_empresa, "Bzu Tech")
        self.assertTrue(user.check_password("SenhaForte123!"))
        self.assertNotEqual(user.password, "SenhaForte123!")
        self.assertIn("_auth_user_id", self.client.session)
        self.assertContains(self.client.get(reverse("home")), "Maria Silva")
        perfil = self.client.get(reverse("perfil"))
        self.assertContains(perfil, "nova@bzu.com")
        self.assertContains(perfil, "Bzu Tech")

    def test_perfil_exige_login_e_exibe_dados(self):
        response = self.client.get(reverse("perfil"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("login")))

        user = get_user_model().objects.create_user(
            username="maria", first_name="Maria Silva", email="maria@bzu.com", password="SenhaForte123!"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("perfil"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maria Silva")
        self.assertContains(response, "maria@bzu.com")
        self.assertContains(response, "Sair")

    def test_sair_desautentica_usuario(self):
        user = get_user_model().objects.create_user(
            username="maria", first_name="Maria Silva", email="maria@bzu.com", password="SenhaForte123!"
        )
        self.client.force_login(user)

        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(self.client.get(reverse("home")), "LOGIN")

    def test_cadastro_recusa_email_duplicado(self):
        User = get_user_model()
        User.objects.create_user(username="existente", email="ja@bzu.com", password="SenhaForte123!")

        resp = self.client.post(
            reverse("conta"),
            {
                "nome": "Outro Nome",
                "email": "JA@bzu.com",
                "empresa": "Outra empresa",
                "senha": "OutraSenha123!",
                "confirmar_senha": "OutraSenha123!",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Este e-mail já está cadastrado.")
        self.assertEqual(User.objects.count(), 1)

    def test_cadastro_recusa_senha_fraca(self):
        resp = self.client.post(
            reverse("conta"),
            {
                "nome": "Maria Silva",
                "email": "nova@bzu.com",
                "empresa": "Bzu Tech",
                "senha": "123",
                "confirmar_senha": "123",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "password")
        self.assertFalse(get_user_model().objects.filter(email="nova@bzu.com").exists())


    def test_cadastro_exige_dados_completos(self):
        resp = self.client.post(
            reverse("conta"),
            {
                "email": "nova@bzu.com",
                "empresa": "Bzu Tech",
                "senha": "SenhaForte123!",
                "confirmar_senha": "SenhaForte123!",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Informe um nome com até 150 caracteres.")
        self.assertFalse(get_user_model().objects.filter(email="nova@bzu.com").exists())

    def test_cadastro_recusa_senhas_diferentes(self):
        response = self.client.post(
            reverse("conta"),
            {
                "nome": "Maria Silva",
                "email": "nova@bzu.com",
                "empresa": "Bzu Tech",
                "senha": "SenhaForte123!",
                "confirmar_senha": "SenhaDiferente123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "As senhas não conferem.")
        self.assertFalse(get_user_model().objects.filter(email="nova@bzu.com").exists())


class QuestionarioViewTests(TestCase):
    def test_questionario_mostra_uma_pergunta_por_etapa(self):
        response = self.client.get(reverse("questionario"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2) Em qual segmento sua empresa atua?")
        self.assertEqual(response.content.decode().count('class="opcao segmento"'), 12)
        self.assertContains(response, 'id="pergunta-segmento" aria-labelledby="titulo-segmento" hidden')
        self.assertContains(response, 'id="navegacao-2" hidden')
        self.assertContains(response, 'id="proxima-pergunta" type="button" disabled')
        self.assertContains(response, 'id="segmento-outro-texto"')
        self.assertContains(response, 'id="finalizar-questionario"')

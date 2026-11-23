/* LOGUS AI — chat (página /chat/ e widget), estado da simulação e download do PDF. */
(function () {
  'use strict';

  const API_CHAT = '/api/chat/';
  const API_SIMULAR = '/api/simular/';
  const URL_PDF = '/relatorio/pdf/';
  const CHAVE_SIM = 'bzu_simulacao';
  const TIMEOUT_MS = 30000;
  const reduzirMovimento = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------------------------------------------------------------- utilitários
  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);

  const inline = (s) =>
    s
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');

  function renderMarkdown(texto) {
    let html = '';
    let lista = false;
    for (const raw of escapeHtml(texto).split('\n')) {
      const linha = raw.trim();
      const item = /^([-*•]|\d+\.)\s+/.exec(linha);
      if (item) {
        if (!lista) { html += '<ul>'; lista = true; }
        html += `<li>${inline(linha.slice(item[0].length))}</li>`;
        continue;
      }
      if (lista) { html += '</ul>'; lista = false; }
      if (linha) html += `<p>${inline(linha.replace(/^#{1,4}\s*/, ''))}</p>`;
    }
    if (lista) html += '</ul>';
    return html || `<p>${escapeHtml(texto)}</p>`;
  }

  async function postJSON(url, corpo, { timeout = TIMEOUT_MS, blob = false } = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(corpo),
        signal: ctrl.signal,
      });
      const dados = blob ? await res.blob() : await res.json();
      return { ok: res.ok, dados, res };
    } finally {
      clearTimeout(timer);
    }
  }

  // ---------------------------------------------------------------- estado compartilhado
  const estado = {
    obter() {
      try {
        const raw = sessionStorage.getItem(CHAVE_SIM);
        if (raw) return JSON.parse(raw);
      } catch (_) {}
      const el = document.getElementById('simulacao-inicial-data') || document.getElementById('resultado-simulacao-data');
      if (el) {
        try { return JSON.parse(el.textContent); } catch (_) {}
      }
      return null;
    },
    definir(sim) {
      if (!sim) return;
      try { sessionStorage.setItem(CHAVE_SIM, JSON.stringify(sim)); } catch (_) {}
      window.dispatchEvent(new CustomEvent('logus:simulacao', { detail: sim }));
    },
  };

  function contextoInicial() {
    const ctx = {};
    try {
      const coleta = sessionStorage.getItem('bzu_coleta');
      if (coleta) ctx.coleta_atual = coleta;
    } catch (_) {}
    const sim = estado.obter();
    if (sim && sim.parametros) Object.assign(ctx, sim.parametros);
    return ctx;
  }

  // ---------------------------------------------------------------- PDF
  async function baixarPDF(botao) {
    const sim = estado.obter();
    const textoOriginal = botao ? botao.innerHTML : '';
    if (botao) { botao.classList.add('carregando'); botao.textContent = 'Gerando PDF...'; }
    try {
      if (!sim || !sim.parametros) { location.href = URL_PDF; return; }
      const { ok, dados, res } = await postJSON(URL_PDF, { parametros: sim.parametros, analises: sim.analises }, { blob: true });
      if (!ok) throw new Error('Falha ao gerar PDF');
      const nome = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') || '')?.[1] || 'LOGUS_AI_Relatorio.pdf';
      const url = URL.createObjectURL(dados);
      const a = Object.assign(document.createElement('a'), { href: url, download: nome });
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (_) {
      location.href = URL_PDF; // fallback: gera a partir da sessão no servidor
    } finally {
      if (botao) { botao.classList.remove('carregando'); botao.innerHTML = textoOriginal; }
    }
  }

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-baixar-pdf]');
    if (btn) { e.preventDefault(); baixarPDF(btn); }
  });

  // ---------------------------------------------------------------- logo
  function animarLogo(svg) {
    if (!svg || reduzirMovimento) return;
    svg.classList.remove('animar');
    void svg.getBoundingClientRect(); // reinicia a animação
    svg.classList.add('animar');
  }

  // ---------------------------------------------------------------- textarea auto-ajustável
  function prepararTextarea(ta, aoEnviar, contador) {
    const max = Number(ta.dataset.max) || 200;
    let agendado = false;
    const ajustar = () => {
      agendado = false;
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight + 2, max) + 'px';
      if (contador) contador.textContent = ta.value.length;
    };
    const agendar = () => { if (!agendado) { agendado = true; requestAnimationFrame(ajustar); } };
    ta.maxLength = 4000;
    ta.addEventListener('input', agendar);
    ta.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        aoEnviar();
      }
    });
    ajustar();
    return agendar;
  }

  // ---------------------------------------------------------------- controlador de chat
  function criarChat({ lista, form, input, chips, contador, aoModoIA }) {
    const historico = [];
    let contexto = contextoInicial();
    let enviando = false;
    const botao = form.querySelector('[type="submit"]');

    const rolar = () => requestAnimationFrame(() => { lista.scrollTop = lista.scrollHeight; });

    function adicionar(papel, texto) {
      const wrap = document.createElement('div');
      wrap.className = `msg ${papel === 'user' ? 'msg-user' : 'msg-bot'}`;
      const bolha = document.createElement('div');
      bolha.className = 'msg-bolha';
      if (papel === 'user') {
        bolha.textContent = texto; // white-space: pre-wrap preserva os parágrafos
      } else {
        bolha.innerHTML = renderMarkdown(texto);
        if (!reduzirMovimento) {
          bolha.classList.add('revelar');
          [...bolha.children].forEach((el, i) => el.style.setProperty('--i', Math.min(i, 14)));
        }
      }
      wrap.appendChild(bolha);
      lista.appendChild(wrap);
      rolar();
      return wrap;
    }

    function digitando() {
      const wrap = document.createElement('div');
      wrap.className = 'msg msg-bot digitando';
      wrap.innerHTML = '<div class="msg-bolha"><span class="pontos"><i></i><i></i><i></i></span>LOGUS AI está analisando...</div>';
      lista.appendChild(wrap);
      rolar();
      return wrap;
    }

    async function enviar(texto) {
      const msg = String(texto ?? input.value).trim();
      if (!msg || enviando) return;
      enviando = true;
      if (botao) botao.disabled = true;
      input.value = '';
      ajustar();
      adicionar('user', msg);
      const indicador = digitando();

      try {
        const { ok, dados } = await postJSON(API_CHAT, { mensagem: msg, contexto, historico: historico.slice(-6) });
        indicador.remove();
        if (!ok) {
          adicionar('assistant', dados.erro || 'Não consegui processar sua solicitação agora. Tente novamente.');
          return;
        }
        adicionar('assistant', dados.resposta);
        historico.push({ role: 'user', content: msg }, { role: 'assistant', content: dados.resposta });
        if (historico.length > 12) historico.splice(0, historico.length - 12);
        if (dados.contexto) contexto = dados.contexto;
        if (dados.simulacao) estado.definir(dados.simulacao);
        if (aoModoIA && dados.modo_ia) aoModoIA(dados.modo_ia);
      } catch (err) {
        indicador.remove();
        adicionar('assistant', err.name === 'AbortError'
          ? 'A análise demorou mais que o esperado. Tente novamente em instantes.'
          : 'Erro de conexão com o servidor. Verifique se o Django está rodando.');
      } finally {
        enviando = false;
        if (botao) botao.disabled = false;
        input.focus({ preventScroll: true });
      }
    }

    const ajustar = prepararTextarea(input, () => enviar(), contador);
    form.addEventListener('submit', (e) => { e.preventDefault(); enviar(); });

    chips?.addEventListener('click', (e) => {
      const chip = e.target.closest('.chip');
      if (!chip) return;
      if (chip.dataset.modelo) {
        input.value =
          'Empresa: \nSegmento: \nHorário/turnos de funcionamento: \nQuantidade de equipamentos ou máquinas: \n' +
          'Conta de energia mensal: R$ \nGasto mensal com manutenção: R$ \nComo coletamos dados hoje: \nPrincipal problema: ';
        ajustar();
        input.focus();
        input.setSelectionRange(9, 9);
        return;
      }
      enviar(chip.dataset.prompt || chip.textContent);
    });

    return {
      enviar,
      adicionar,
      definirContexto(ctx) { contexto = { ...contexto, ...ctx }; },
    };
  }

  const rotuloModo = (modo) => (modo === 'gemini' ? 'LOGUS AI · Gemini ativo' : 'LOGUS AI · motor preditivo');

  // ---------------------------------------------------------------- página /chat/
  const formPagina = document.getElementById('chat-page-form');
  if (formPagina) {
    const setText = (id, valor) => {
      const el = document.getElementById(id);
      if (!el || valor == null || el.textContent === String(valor)) return;
      el.textContent = valor;
      if (el.tagName === 'STRONG' && !reduzirMovimento) {
        el.classList.remove('atualizado');
        void el.offsetWidth;
        el.classList.add('atualizado');
      }
    };

    const listaDisp = document.getElementById('painel-lista-dispositivos');
    const btnPdf = document.getElementById('btn-painel-pdf');
    const btnResultado = document.getElementById('btn-painel-resultado');

    const zerarPainel = () => {
      setText('painel-empresa', 'Aguardando dados');
      setText('painel-pacote', '--');
      setText('painel-cenario', 'Informe os dados da sua operação no chat ou no formulário acima para gerar a análise.');
      setText('kpi-economia', 'R$ 0');
      setText('kpi-roi', '0%');
      setText('kpi-payback', '0 meses');
      setText('kpi-capex', 'R$ 0');
      setText('perfil-resumo', 'Não preenchido');
      if (listaDisp) {
        listaDisp.innerHTML = '<p class="lista-vazia">Nenhum dispositivo sugerido ainda. Envie as informações da sua operação para a LOGUS AI calcular.</p>';
      }
      if (btnPdf) btnPdf.disabled = true;
      if (btnResultado) btnResultado.classList.add('desabilitado');
    };

    const atualizarPainel = (sim) => {
      if (!sim || !sim.formatado) {
        zerarPainel();
        return;
      }
      setText('painel-empresa', sim.titulo_empresa || sim.parametros?.empresa || 'Sua operação');
      setText('painel-pacote', sim.pacote_recomendado);
      setText('painel-cenario', sim.subtitulo_cenario);
      setText('kpi-economia', sim.formatado.economia_anual);
      setText('kpi-roi', sim.formatado.roi_12m);
      setText('kpi-payback', sim.formatado.payback);
      setText('kpi-capex', sim.formatado.investimento_inicial);
      setText('perfil-resumo', sim.parametros?.empresa || 'Preenchido');
      if (listaDisp && Array.isArray(sim.dispositivos_sugeridos) && sim.dispositivos_sugeridos.length) {
        listaDisp.innerHTML = sim.dispositivos_sugeridos
          .map((d) => `<div class="disp-item"><div class="disp-item-topo"><strong>${escapeHtml(d.codigo)} — ${escapeHtml(d.categoria)}</strong><span class="disp-qtd">${Number(d.quantidade)}x</span></div><p>${escapeHtml(d.resumo)}</p></div>`)
          .join('');
      }
      if (btnPdf) btnPdf.disabled = false;
      if (btnResultado) btnResultado.classList.remove('desabilitado');
    };

    window.addEventListener('logus:simulacao', (e) => atualizarPainel(e.detail));
    // Só preenche inicialmente se o servidor tiver uma simulação real já feita nesta sessão
    let simServidor = null;
    const elSim = document.getElementById('simulacao-inicial-data');
    if (elSim) {
      try { simServidor = JSON.parse(elSim.textContent); } catch (_) {}
    }
    if (simServidor) {
      estado.definir(simServidor);
      atualizarPainel(simServidor);
    } else {
      try { sessionStorage.removeItem(CHAVE_SIM); } catch (_) {}
      zerarPainel();
    }

    const chat = criarChat({
      lista: document.getElementById('chat-page-mensagens'),
      form: formPagina,
      input: document.getElementById('chat-page-input'),
      chips: document.getElementById('chat-page-sugestoes'),
      contador: document.getElementById('chat-contador'),
      aoModoIA: (modo) => {
        const badge = document.getElementById('badge-modo-ia');
        if (badge) badge.innerHTML = `<i class="pulso"></i>${rotuloModo(modo)}`;
      },
    });

    // Formulário "Dados da empresa"
    const formPerfil = document.getElementById('form-perfil');
    formPerfil?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = formPerfil.querySelector('[type="submit"]');
      btn.classList.add('carregando');
      btn.textContent = 'Aplicando...';
      const dados = Object.fromEntries(new FormData(formPerfil));
      const anterior = estado.obter()?.parametros || {};
      if (anterior.descricao_operacao) dados.descricao_operacao = anterior.descricao_operacao;
      try {
        const { ok, dados: sim } = await postJSON(API_SIMULAR, dados);
        if (!ok) throw new Error();
        estado.definir(sim);
        chat.definirContexto(sim.parametros);
        const nome = sim.parametros.empresa || 'sua operação';
        chat.adicionar('assistant',
          `Perfil de **${nome}** aplicado (${sim.parametros.modo_rotulo.toLowerCase()}).\n` +
          `- **Economia anual:** ${sim.formatado.economia_anual}\n- **ROI em 12 meses:** ${sim.formatado.roi_12m}\n` +
          `- **Payback:** ${sim.formatado.payback}\n\nVocê já pode baixar o relatório em PDF ou continuar a conversa.`);
      } catch (_) {
        chat.adicionar('assistant', 'Não consegui aplicar os dados da empresa agora. Tente novamente.');
      } finally {
        btn.classList.remove('carregando');
        btn.textContent = 'Aplicar à análise';
      }
    });
  }

  // ---------------------------------------------------------------- widget flutuante
  const fab = document.getElementById('bzu-chat-fab');
  const drawer = document.getElementById('bzu-chat-drawer');
  const formWidget = document.getElementById('bzu-widget-form');
  if (fab && drawer && formWidget && !formPagina) {
    const input = document.getElementById('bzu-widget-input');
    const logoHeader = drawer.querySelector('.logo-widget');
    let aberto = false;

    const alternar = (abrir = !aberto) => {
      aberto = abrir;
      drawer.classList.toggle('aberto', abrir);
      drawer.toggleAttribute('inert', !abrir);
      drawer.setAttribute('aria-hidden', String(!abrir));
      fab.setAttribute('aria-expanded', String(abrir));
      if (abrir) {
        animarLogo(logoHeader);
        animarLogo(fab.querySelector('.logus-logo'));
        setTimeout(() => input.focus({ preventScroll: true }), 220);
      }
    };

    fab.addEventListener('click', () => alternar());
    document.getElementById('bzu-chat-close')?.addEventListener('click', () => alternar(false));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && aberto) alternar(false); });
    document.querySelectorAll('[data-abrir-chat]').forEach((b) => b.addEventListener('click', () => alternar(true)));

    criarChat({
      lista: document.getElementById('bzu-widget-mensagens'),
      form: formWidget,
      input,
      chips: document.getElementById('bzu-widget-chips'),
      aoModoIA: (modo) => {
        const sub = document.getElementById('bzu-widget-modo');
        if (sub) sub.textContent = rotuloModo(modo);
      },
    });
  }

  window.LogusAI = { estado, baixarPDF, escapeHtml, renderMarkdown, postJSON, animarLogo };
})();

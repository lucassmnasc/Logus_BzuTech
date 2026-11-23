(function () {
  const API_CHAT = '/api/chat/';

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderMarkdown(texto) {
    const linhas = escapeHtml(texto).split('\n');
    let html = '';
    let emLista = false;

    const formatarInline = (s) =>
      s
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code>$1</code>');

    for (const raw of linhas) {
      const linha = raw.trim();
      if (linha.startsWith('- ') || linha.startsWith('* ')) {
        if (!emLista) {
          html += '<ul>';
          emLista = true;
        }
        html += `<li>${formatarInline(linha.slice(2))}</li>`;
      } else {
        if (emLista) {
          html += '</ul>';
          emLista = false;
        }
        if (linha) {
          html += `<p>${formatarInline(linha)}</p>`;
        }
      }
    }
    if (emLista) html += '</ul>';
    return html || `<p>${escapeHtml(texto)}</p>`;
  }

  function carregarContextoSessao() {
    const ctx = {};
    try {
      const coleta = sessionStorage.getItem('bzu_coleta');
      if (coleta) ctx.coleta_atual = coleta;

      const leadRaw = sessionStorage.getItem('bzu_lead');
      if (leadRaw) {
        const lead = JSON.parse(leadRaw);
        if (lead.dispositivos) ctx.qtd_dispositivos = Number(lead.dispositivos);
        if (lead.endpoint) ctx.endpoint_preferido = lead.endpoint;
        if (lead.empresa) ctx.empresa = lead.empresa;
      }

      const simRaw = sessionStorage.getItem('bzu_simulacao');
      if (simRaw) {
        const sim = JSON.parse(simRaw);
        if (sim && sim.parametros) Object.assign(ctx, sim.parametros);
      }
    } catch (_) {}
    return ctx;
  }

  function salvarSimulacao(simulacao) {
    if (!simulacao) return;
    try {
      sessionStorage.setItem('bzu_simulacao', JSON.stringify(simulacao));
    } catch (_) {}
  }

  function criarControllerChat({ containerMensagens, form, input, chipsContainer, onSimulacaoAtualizada, onModoIA }) {
    const historico = [];
    let contexto = carregarContextoSessao();
    let enviando = false;

    function adicionarMensagem(papel, texto, loading = false) {
      const wrapper = document.createElement('div');
      wrapper.className = `msg ${papel === 'user' ? 'msg-user' : 'msg-bot'}${loading ? ' msg-loading' : ''}`;
      const bolha = document.createElement('div');
      bolha.className = 'msg-bolha';
      bolha.innerHTML = papel === 'user' ? `<p>${escapeHtml(texto)}</p>` : renderMarkdown(texto);
      wrapper.appendChild(bolha);
      containerMensagens.appendChild(wrapper);
      containerMensagens.scrollTop = containerMensagens.scrollHeight;
      return wrapper;
    }

    async function enviarMensagem(texto) {
      const msg = (texto || '').trim();
      if (!msg || enviando) return;
      enviando = true;
      input.value = '';

      adicionarMensagem('user', msg);
      const loadingEl = adicionarMensagem('assistant', 'Analisando operação e calculando ROI...', true);

      try {
        const res = await fetch(API_CHAT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            mensagem: msg,
            contexto,
            historico: historico.slice(-8),
          }),
        });

        const data = await res.json();
        loadingEl.remove();

        if (!res.ok) {
          adicionarMensagem('assistant', data.erro || 'Não consegui processar sua solicitação agora. Tente novamente.');
        } else {
          adicionarMensagem('assistant', data.resposta);
          historico.push({ role: 'user', content: msg });
          historico.push({ role: 'assistant', content: data.resposta });
          if (data.contexto) contexto = data.contexto;
          if (data.simulacao) {
            salvarSimulacao(data.simulacao);
            if (typeof onSimulacaoAtualizada === 'function') {
              onSimulacaoAtualizada(data.simulacao);
            }
          }
          if (typeof onModoIA === 'function' && data.modo_ia) {
            onModoIA(data.modo_ia);
          }
        }
      } catch (_) {
        loadingEl.remove();
        adicionarMensagem('assistant', 'Erro de conexão com o servidor Django. Verifique se o servidor está rodando.');
      } finally {
        enviando = false;
        input.focus();
      }
    }

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      enviarMensagem(input.value);
    });

    if (chipsContainer) {
      chipsContainer.querySelectorAll('.chip').forEach((btn) => {
        btn.addEventListener('click', () => {
          enviarMensagem(btn.dataset.prompt || btn.textContent);
        });
      });
    }

    return { enviarMensagem };
  }

  // 1. Inicialização da página dedicada /chat/
  const pageForm = document.getElementById('chat-page-form');
  if (pageForm) {
    const atualizarPainel = (sim) => {
      if (!sim || !sim.formatado) return;
      const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };
      setText('painel-pacote', sim.pacote_recomendado || 'Business IoT');
      setText('painel-cenario', sim.subtitulo_cenario || '');
      setText('kpi-economia', sim.formatado.economia_anual);
      setText('kpi-roi', sim.formatado.roi_12m);
      setText('kpi-payback', sim.formatado.payback);
      setText('kpi-capex', sim.formatado.investimento_inicial);

      const lista = document.getElementById('painel-lista-dispositivos');
      if (lista && Array.isArray(sim.dispositivos_sugeridos)) {
        lista.innerHTML = sim.dispositivos_sugeridos
          .map(
            (d) => `
            <div class="disp-item">
              <div class="disp-item-topo">
                <strong>${escapeHtml(d.codigo)} — ${escapeHtml(d.categoria)}</strong>
                <span class="disp-qtd">${d.quantidade}x</span>
              </div>
              <p>${escapeHtml(d.resumo)}</p>
            </div>`
          )
          .join('');
      }
    };

    // Carrega simulação inicial do sessionStorage ou do servidor
    let simInicial = null;
    try {
      const saved = sessionStorage.getItem('bzu_simulacao');
      if (saved) simInicial = JSON.parse(saved);
    } catch (_) {}
    if (!simInicial) {
      const dataEl = document.getElementById('simulacao-inicial-data');
      if (dataEl) {
        try {
          simInicial = JSON.parse(dataEl.textContent);
        } catch (_) {}
      }
    }
    if (simInicial) atualizarPainel(simInicial);

    criarControllerChat({
      containerMensagens: document.getElementById('chat-page-mensagens'),
      form: pageForm,
      input: document.getElementById('chat-page-input'),
      chipsContainer: document.getElementById('chat-page-sugestoes'),
      onSimulacaoAtualizada: atualizarPainel,
      onModoIA: (modo) => {
        const badge = document.getElementById('badge-modo-ia');
        if (badge) {
          badge.textContent = modo === 'gemini' ? 'Consultor IA • Gemini ativo' : 'Consultor IA • Motor Preditivo Local';
        }
      },
    });
  }

  // 2. Inicialização do widget flutuante em todas as outras telas
  const fab = document.getElementById('bzu-chat-fab');
  const drawer = document.getElementById('bzu-chat-drawer');
  const widgetForm = document.getElementById('bzu-widget-form');
  if (fab && drawer && widgetForm) {
    const toggleDrawer = (abrir) => {
      const novoEstado = typeof abrir === 'boolean' ? abrir : drawer.hidden;
      drawer.hidden = !novoEstado;
      fab.setAttribute('aria-expanded', String(novoEstado));
      if (novoEstado) {
        document.getElementById('bzu-widget-input')?.focus();
      }
    };

    fab.addEventListener('click', () => toggleDrawer());
    document.getElementById('bzu-chat-close')?.addEventListener('click', () => toggleDrawer(false));

    // Permite que botões na página (como em /resultado/) abram o chat
    document.querySelectorAll('[data-abrir-chat]').forEach((btn) => {
      btn.addEventListener('click', () => toggleDrawer(true));
    });

    criarControllerChat({
      containerMensagens: document.getElementById('bzu-widget-mensagens'),
      form: widgetForm,
      input: document.getElementById('bzu-widget-input'),
      chipsContainer: document.getElementById('bzu-widget-chips'),
      onModoIA: (modo) => {
        const sub = document.getElementById('bzu-widget-modo');
        if (sub) {
          sub.textContent = modo === 'gemini' ? 'Gemini IA • Online' : 'Motor Preditivo Bzu • Online';
        }
      },
    });
  }
})();

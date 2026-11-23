// clicar em um indicador rola até o detalhamento correspondente
document.querySelector('.indicadores')?.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-alvo]');
  if (btn) document.querySelector(btn.dataset.alvo)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

(function () {
  const L = window.LogusAI;
  if (!L) return;
  const { escapeHtml } = L;

  const setText = (id, val) => {
    const el = document.getElementById(id);
    if (el && val != null && el.textContent !== String(val)) el.textContent = val;
  };

  function aplicar(sim) {
    if (!sim || !sim.formatado) return;
    const p = sim.parametros || {};
    setText('res-empresa', sim.titulo_empresa || p.empresa || 'Sua operação');
    setText('tag-segmento', p.segmento_rotulo);
    setText('tag-modo', p.modo_rotulo);
    const cidade = document.getElementById('tag-cidade');
    if (cidade) { cidade.textContent = p.cidade || ''; cidade.hidden = !p.cidade; }

    const sub = document.getElementById('res-subtitulo');
    if (sub && sim.subtitulo_cenario) sub.innerHTML = `${escapeHtml(sim.subtitulo_cenario)}<br>Clique em cada indicador para explorar.`;

    for (const [card, chave] of [['economia', 'economia_anual'], ['roi', 'roi_12m'], ['payback', 'payback'], ['eficiencia', 'reducao_energia']]) {
      setText(`card-${card}`, sim.formatado[chave]);
      setText(`val-${card}`, sim.formatado[chave]);
      if (sim.analises) setText(`txt-${card}`, sim.analises[card]);
    }
    setText('res-qtd-pontos', p.qtd_dispositivos);
    setText('res-pacote', sim.pacote_recomendado);
    setText('res-capex', sim.formatado.investimento_inicial);

    const grid = document.getElementById('res-dispositivos-grid');
    if (grid && Array.isArray(sim.dispositivos_sugeridos)) {
      grid.innerHTML = sim.dispositivos_sugeridos
        .map((d) => `<article class="sug-card"><div class="sug-card-topo"><span class="sug-codigo">${escapeHtml(d.codigo)}</span><span class="sug-qtd">${Number(d.quantidade)} unidades (${Number(d.percentual_mix)}%)</span></div><h3>${escapeHtml(d.categoria)}</h3><p>${escapeHtml(d.resumo)}</p></article>`)
        .join('');
    }
  }

  const sim = L.estado.obter();
  aplicar(sim);

  // Textos personalizados com Gemini são buscados em segundo plano (a página não espera por eles)
  if (sim && sim.parametros && sim.modo_ia !== 'gemini') {
    const selo = document.getElementById('selo-texto');
    const buscar = async () => {
      if (selo) selo.textContent = 'LOGUS AI refinando análise...';
      try {
        const { ok, dados } = await L.postJSON('/api/analises-ia/', { parametros: sim.parametros }, { timeout: 25000 });
        if (ok && dados.modo_ia === 'gemini' && dados.analises) {
          document.querySelectorAll('.txt-ia').forEach((el) => el.classList.add('trocando'));
          setTimeout(() => {
            sim.analises = dados.analises;
            sim.modo_ia = 'gemini';
            L.estado.definir(sim);
            aplicar(sim);
            document.querySelectorAll('.txt-ia').forEach((el) => el.classList.remove('trocando'));
          }, 250);
        }
      } catch (_) {
        /* mantém a análise local */
      } finally {
        if (selo) selo.textContent = 'Análise concluída';
      }
    };
    (window.requestIdleCallback || ((fn) => setTimeout(fn, 300)))(buscar);
  }
})();

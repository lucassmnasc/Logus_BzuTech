// clicar em um indicador rola até o detalhamento correspondente
document.querySelectorAll('[data-alvo]').forEach(btn =>
  btn.addEventListener('click', () =>
    document.querySelector(btn.dataset.alvo)?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
);

// sincroniza a tela com a simulação mais recente do sessionStorage (vinda do configurar ou do chat)
(function () {
  let sim = null;
  try {
    const raw = sessionStorage.getItem('bzu_simulacao');
    if (raw) sim = JSON.parse(raw);
  } catch (_) {}

  if (!sim || !sim.formatado) return;

  const setText = (id, val) => {
    const el = document.getElementById(id);
    if (el && val !== undefined && val !== null) el.textContent = val;
  };

  const escapeHtml = (s) =>
    String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');

  const sub = document.getElementById('res-subtitulo');
  if (sub && sim.subtitulo_cenario) {
    sub.innerHTML = `${escapeHtml(sim.subtitulo_cenario)}<br>Clique em cada indicador para explorar.`;
  }

  setText('card-economia', sim.formatado.economia_anual);
  setText('card-roi', sim.formatado.roi_12m);
  setText('card-payback', sim.formatado.payback);
  setText('card-eficiencia', sim.formatado.reducao_energia);

  setText('val-economia', sim.formatado.economia_anual);
  setText('val-roi', sim.formatado.roi_12m);
  setText('val-payback', sim.formatado.payback);
  setText('val-eficiencia', sim.formatado.reducao_energia);

  if (sim.analises) {
    setText('txt-economia', sim.analises.economia);
    setText('txt-roi', sim.analises.roi);
    setText('txt-payback', sim.analises.payback);
    setText('txt-eficiencia', sim.analises.eficiencia);
  }

  if (sim.parametros) {
    setText('res-qtd-pontos', sim.parametros.qtd_dispositivos);
  }
  setText('res-pacote', sim.pacote_recomendado);
  setText('res-capex', sim.formatado.investimento_inicial);

  const grid = document.getElementById('res-dispositivos-grid');
  if (grid && Array.isArray(sim.dispositivos_sugeridos)) {
    grid.innerHTML = sim.dispositivos_sugeridos
      .map(
        (d) => `
        <article class="sug-card">
          <div class="sug-card-topo">
            <span class="sug-codigo">${escapeHtml(d.codigo)}</span>
            <span class="sug-qtd">${d.quantidade} unidades (${d.percentual_mix}%)</span>
          </div>
          <h3>${escapeHtml(d.categoria)}</h3>
          <p>${escapeHtml(d.resumo)}</p>
        </article>`
      )
      .join('');
  }
})();

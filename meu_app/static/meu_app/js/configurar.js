const qtd = document.getElementById('qtd');
const badge = document.getElementById('valor-disp');
const resumo = document.getElementById('res-disp');
const form = document.getElementById('form-lead');

let agendado = false;
function atualizar() {
  agendado = false;
  const pct = ((qtd.value - qtd.min) / (qtd.max - qtd.min)) * 100;
  qtd.style.setProperty('--pct', pct + '%');
  badge.textContent = resumo.textContent = qtd.value;
}
// atualiza no máximo 1x por quadro enquanto o slider é arrastado
qtd.addEventListener('input', () => { if (!agendado) { agendado = true; requestAnimationFrame(atualizar); } });
atualizar();

// seleção do endpoint
const endpoints = document.querySelector('.endpoints');
endpoints?.addEventListener('click', (e) => {
  const ep = e.target.closest('.endpoint');
  if (!ep) return;
  endpoints.querySelectorAll('.endpoint').forEach((o) => o.classList.toggle('ativo', o === ep));
});

document.querySelectorAll('[data-scroll]').forEach((btn) =>
  btn.addEventListener('click', () => document.querySelector(btn.dataset.scroll)?.scrollIntoView({ behavior: 'smooth' }))
);

// restaura respostas anteriores (questionário + formulário)
try {
  const coleta = sessionStorage.getItem('bzu_coleta');
  if (coleta && form.coleta_atual) form.coleta_atual.value = coleta;
  const lead = JSON.parse(sessionStorage.getItem('bzu_lead') || 'null');
  if (lead) {
    for (const [k, v] of Object.entries(lead)) {
      if (form.elements[k] && v && k !== 'coleta_atual') form.elements[k].value = v;
    }
    if (lead.dispositivos) { qtd.value = lead.dispositivos; atualizar(); }
    if (lead.endpoint) document.querySelector(`.endpoint[data-ep="${lead.endpoint}"]`)?.classList.add('ativo');
  }
} catch (_) {}

// envio: calcula a simulação no Django e segue para /resultado/
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = form.querySelector('button[type="submit"]');
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.textContent = 'LOGUS AI calculando...';

  const dados = Object.fromEntries(new FormData(form));
  dados.dispositivos = Number(qtd.value);
  dados.endpoint = document.querySelector('.endpoint.ativo')?.dataset.ep || '';
  try {
    sessionStorage.setItem('bzu_lead', JSON.stringify(dados));
    sessionStorage.setItem('bzu_coleta', dados.coleta_atual);
  } catch (_) {}

  try {
    const resp = await fetch('/api/simular/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (resp.ok) {
      const sim = await resp.json();
      try { sessionStorage.setItem('bzu_simulacao', JSON.stringify(sim)); } catch (_) {}
    }
  } catch (_) {
    // em falha de rede, /resultado/ usa a última simulação da sessão do servidor
  } finally {
    btn.disabled = false;
    btn.innerHTML = original;
    location.href = document.getElementById('url-resultado').dataset.url;
  }
});

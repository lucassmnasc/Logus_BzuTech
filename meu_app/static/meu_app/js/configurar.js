const qtd = document.getElementById('qtd');
const badge = document.getElementById('valor-disp');
const resumo = document.getElementById('res-disp');

function atualizar() {
  const pct = ((qtd.value - qtd.min) / (qtd.max - qtd.min)) * 100;
  qtd.style.setProperty('--pct', pct + '%');
  badge.textContent = resumo.textContent = qtd.value;
}
qtd.addEventListener('input', atualizar);
atualizar();

// seleção do endpoint
document.querySelectorAll('.endpoint').forEach(ep =>
  ep.addEventListener('click', () => {
    document.querySelectorAll('.endpoint').forEach(o => o.classList.toggle('ativo', o === ep));
  })
);

document.querySelectorAll('[data-scroll]').forEach(btn =>
  btn.addEventListener('click', () => document.querySelector(btn.dataset.scroll)?.scrollIntoView({ behavior: 'smooth' }))
);

// envio do formulário: envia para a API de IA/Simulação do Django e segue para /resultado/
document.getElementById('form-lead').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector('button[type="submit"]');
  const textoOriginal = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Calculando com IA...';
  }

  const dados = Object.fromEntries(new FormData(e.target));
  dados.dispositivos = Number(qtd.value);
  dados.endpoint = document.querySelector('.endpoint.ativo')?.dataset.ep || '';
  try {
    dados.coleta_atual = sessionStorage.getItem('bzu_coleta') || 'planilha-manual';
    sessionStorage.setItem('bzu_lead', JSON.stringify(dados));
  } catch (_) {}

  try {
    const resp = await fetch('/api/simular/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    });
    if (resp.ok) {
      const simulacao = await resp.json();
      try {
        sessionStorage.setItem('bzu_simulacao', JSON.stringify(simulacao));
      } catch (_) {}
    }
  } catch (_) {
    // Caso haja falha de rede, a página de resultado usa os dados do backend
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = textoOriginal;
    }
    location.href = document.getElementById('url-resultado').dataset.url;
  }
});

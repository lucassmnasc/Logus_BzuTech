// Mantém o resumo e o badge do slider sincronizados com as escolhas.
const $ = s => document.querySelector(s);
const qtd = $('#qtd');

function atualizarQtd() {
  const pct = ((qtd.value - qtd.min) / (qtd.max - qtd.min)) * 100;
  qtd.style.setProperty('--pct', pct + '%');
  $('#badge').textContent = $('#res-qtd').textContent = qtd.value;
}
qtd.addEventListener('input', atualizarQtd);
atualizarQtd();

const destinos = { segmento: '#res-seg', tempo: '#res-tempo', pacote: '#res-pacote' };
document.querySelectorAll('input[type=radio]').forEach(r =>
  r.addEventListener('change', () => { $(destinos[r.name]).textContent = r.value; })
);

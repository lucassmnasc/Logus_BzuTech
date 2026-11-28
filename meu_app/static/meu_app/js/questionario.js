const opcoesColeta = [...document.querySelectorAll('.opcao[data-valor]')];
const opcoesSegmento = [...document.querySelectorAll('.opcao[data-segmento]')];
const perguntaColeta = document.querySelector('.pergunta');
const perguntaSegmento = document.getElementById('pergunta-segmento');
const navegacaoColeta = document.getElementById('navegacao-1');
const navegacaoSegmento = document.getElementById('navegacao-2');
const proximaPergunta = document.getElementById('proxima-pergunta');
const perguntaAnterior = document.getElementById('pergunta-anterior');
const finalizar = document.getElementById('finalizar-questionario');
const outros = opcoesSegmento.find(op => op.dataset.segmento === 'outros');
const outrosDetalhe = document.getElementById('outro-detalhe');
const outrosTexto = document.getElementById('segmento-outro-texto');

function mostrarPergunta(numero) {
  const segunda = numero === 2;
  perguntaColeta.hidden = segunda;
  navegacaoColeta.hidden = segunda;
  perguntaSegmento.hidden = !segunda;
  navegacaoSegmento.hidden = !segunda;
  try { sessionStorage.setItem('bzu_questionario_etapa', String(numero)); } catch (_) {}
}

function atualizarSegmentos() {
  const outrosSelecionado = outros.getAttribute('aria-pressed') === 'true';
  outrosDetalhe.hidden = !outrosSelecionado;
  outrosTexto.required = outrosSelecionado;
  outrosTexto.setCustomValidity(
    outrosSelecionado && !outrosTexto.value.trim() ? 'Descreva o segmento selecionado.' : ''
  );
  finalizar.disabled = !opcoesSegmento.some(op => op.getAttribute('aria-pressed') === 'true');
  try {
    const selecionados = opcoesSegmento
      .filter(op => op.getAttribute('aria-pressed') === 'true')
      .map(op => op.dataset.segmento);
    sessionStorage.setItem('bzu_segmentos', JSON.stringify(selecionados));
    sessionStorage.setItem('bzu_segmento_outro', outrosTexto.value.trim());
  } catch (_) {}
}

opcoesColeta.forEach(op => op.addEventListener('click', () => {
  opcoesColeta.forEach(item => item.setAttribute('aria-checked', String(item === op)));
  proximaPergunta.disabled = false;
  try { sessionStorage.setItem('bzu_coleta', op.dataset.valor); } catch (_) {}
}));

opcoesSegmento.forEach(op => op.addEventListener('click', () => {
  const selecionado = op.getAttribute('aria-pressed') === 'true';
  op.setAttribute('aria-pressed', String(!selecionado));
  atualizarSegmentos();
}));

outrosTexto.addEventListener('input', atualizarSegmentos);
proximaPergunta.addEventListener('click', () => mostrarPergunta(2));
perguntaAnterior.addEventListener('click', () => mostrarPergunta(1));
finalizar.addEventListener('click', () => {
  if (outros.getAttribute('aria-pressed') === 'true' && !outrosTexto.checkValidity()) {
    outrosTexto.reportValidity();
    outrosTexto.focus();
    return;
  }
  window.location.assign(finalizar.dataset.url);
});

try {
  const coletaSalva = sessionStorage.getItem('bzu_coleta');
  const coleta = opcoesColeta.find(op => op.dataset.valor === coletaSalva);
  if (coleta) {
    coleta.setAttribute('aria-checked', 'true');
    proximaPergunta.disabled = false;
  }

  const segmentosSalvos = JSON.parse(sessionStorage.getItem('bzu_segmentos') || '[]');
  opcoesSegmento.forEach(op => {
    op.setAttribute('aria-pressed', String(segmentosSalvos.includes(op.dataset.segmento)));
  });
  outrosTexto.value = sessionStorage.getItem('bzu_segmento_outro') || '';
  atualizarSegmentos();
  mostrarPergunta(sessionStorage.getItem('bzu_questionario_etapa') === '2' ? 2 : 1);
} catch (_) {
  mostrarPergunta(1);
}

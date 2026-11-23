// Fundo animado de rede (nós + conexões) — versão otimizada.
// - brilho pré-renderizado em sprite (sem createRadialGradient por quadro)
// - linhas agrupadas por opacidade (poucas chamadas de stroke por quadro)
// - ~30 fps, pausa quando a aba não está visível e sem leituras de layout por quadro
(() => {
  const c = document.getElementById('bg');
  if (!c) return;
  const ctx = c.getContext('2d', { alpha: true });
  const reduzir = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const ALCANCE = 170;
  const ALCANCE2 = ALCANCE * ALCANCE;
  const NIVEIS = 6; // faixas de opacidade das linhas
  const INTERVALO = 1000 / 30;

  let w = 0, h = 0, nos = [], rodando = false, ultimo = 0, raf = 0;

  // sprite do brilho
  const SPRITE_R = 24;
  const sprite = document.createElement('canvas');
  sprite.width = sprite.height = SPRITE_R * 2;
  (() => {
    const s = sprite.getContext('2d');
    const g = s.createRadialGradient(SPRITE_R, SPRITE_R, 0, SPRITE_R, SPRITE_R, SPRITE_R);
    g.addColorStop(0, 'rgba(192,75,219,1)');
    g.addColorStop(1, 'rgba(192,75,219,0)');
    s.fillStyle = g;
    s.fillRect(0, 0, SPRITE_R * 2, SPRITE_R * 2);
  })();

  const caminhos = Array.from({ length: NIVEIS }, () => []);
  const estilos = Array.from({ length: NIVEIS }, (_, i) => `rgba(122,27,140,${(0.5 * (i + 1)) / NIVEIS})`);

  function iniciar() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = window.innerWidth;
    h = window.innerHeight;
    if (w <= 0 || h <= 0) return;
    c.width = Math.round(w * dpr);
    c.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const n = Math.min(w < 700 ? 40 : 75, Math.floor((w * h) / 19000));
    nos = Array.from({ length: n }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5,
      r: 1.5 + Math.random() * 2.5,
      p: Math.random() * 6.28,
    }));
  }

  function desenhar(t) {
    ctx.clearRect(0, 0, w, h);
    for (const lista of caminhos) lista.length = 0;

    const total = nos.length;
    for (let i = 0; i < total; i++) {
      const a = nos[i];
      for (let j = i + 1; j < total; j++) {
        const b = nos[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d2 = dx * dx + dy * dy;
        if (d2 < ALCANCE2) {
          const nivel = Math.min(NIVEIS - 1, Math.floor((1 - Math.sqrt(d2) / ALCANCE) * NIVEIS));
          caminhos[nivel].push(a.x, a.y, b.x, b.y);
        }
      }
    }

    ctx.lineWidth = 1;
    for (let k = 0; k < NIVEIS; k++) {
      const seg = caminhos[k];
      if (!seg.length) continue;
      ctx.strokeStyle = estilos[k];
      ctx.beginPath();
      for (let s = 0; s < seg.length; s += 4) {
        ctx.moveTo(seg[s], seg[s + 1]);
        ctx.lineTo(seg[s + 2], seg[s + 3]);
      }
      ctx.stroke();
    }

    ctx.fillStyle = '#C04BDB';
    ctx.beginPath();
    const destaques = [];
    for (const n of nos) {
      const pulso = (Math.sin(t / 900 + n.p) + 1) / 2;
      const raio = n.r * 6;
      ctx.globalAlpha = 0.35 + 0.25 * pulso;
      ctx.drawImage(sprite, n.x - raio, n.y - raio, raio * 2, raio * 2);
      if (pulso > 0.9) destaques.push(n);
    }
    ctx.globalAlpha = 1;
    for (const n of nos) {
      ctx.moveTo(n.x + n.r, n.y);
      ctx.arc(n.x, n.y, n.r, 0, 6.283);
    }
    ctx.fill();
    if (destaques.length) {
      ctx.fillStyle = '#F3D9FA';
      ctx.beginPath();
      for (const n of destaques) {
        ctx.moveTo(n.x + n.r, n.y);
        ctx.arc(n.x, n.y, n.r, 0, 6.283);
      }
      ctx.fill();
    }
  }

  function mover() {
    for (const n of nos) {
      n.x += n.vx;
      n.y += n.vy;
      if (n.x < 0 || n.x > w) n.vx *= -1;
      if (n.y < 0 || n.y > h) n.vy *= -1;
    }
  }

  function quadro(t) {
    if (!rodando) return;
    raf = requestAnimationFrame(quadro);
    if (t - ultimo < INTERVALO) return;
    ultimo = t;
    mover();
    desenhar(t);
  }

  function iniciarLoop() {
    if (rodando || reduzir) return;
    rodando = true;
    raf = requestAnimationFrame(quadro);
  }

  function pararLoop() {
    rodando = false;
    cancelAnimationFrame(raf);
  }

  let timerResize = 0;
  window.addEventListener('resize', () => {
    clearTimeout(timerResize);
    timerResize = setTimeout(() => { iniciar(); desenhar(performance.now()); }, 150);
  }, { passive: true });

  document.addEventListener('visibilitychange', () => (document.hidden ? pararLoop() : iniciarLoop()));

  iniciar();
  desenhar(0);
  iniciarLoop();
})();

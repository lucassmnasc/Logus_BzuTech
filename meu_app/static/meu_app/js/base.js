// Fundo animado de rede (nós + conexões) — cores do protótipo Figma
(() => {
  const c = document.getElementById('bg');
  if (!c) return;
  const ctx = c.getContext('2d');
  const reduzir = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let w = 0, h = 0, dAtual = 0, nos = [];

  function iniciar() {
    const novaLargura = c.clientWidth || window.innerWidth;
    const novaAltura = c.clientHeight || window.innerHeight;

    if (novaLargura <= 0 || novaAltura <= 0) return;

    dAtual = window.devicePixelRatio || 1;
    w = novaLargura;
    h = novaAltura;

    c.width = Math.round(w * dAtual);
    c.height = Math.round(h * dAtual);
    ctx.setTransform(dAtual, 0, 0, dAtual, 0, 0);

    const n = Math.min(90, Math.floor((w * h) / 16000));
    nos = Array.from({ length: n }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
      r: 1.5 + Math.random() * 2.5,
      p: Math.random() * 6.28,
    }));
  }

  function quadro(t) {
    const larguraAtual = c.clientWidth || window.innerWidth;
    const alturaAtual = c.clientHeight || window.innerHeight;

    if (
      nos.length === 0 ||
      Math.abs(w - larguraAtual) > 1 ||
      Math.abs(h - alturaAtual) > 1 ||
      dAtual !== (window.devicePixelRatio || 1)
    ) {
      iniciar();
    }

    if (w > 0 && h > 0) {
      ctx.clearRect(0, 0, w, h);
      const alcance = 170;

      for (let i = 0; i < nos.length; i++) {
        for (let j = i + 1; j < nos.length; j++) {
          const a = nos[i], b = nos[j], d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < alcance) {
            ctx.strokeStyle = `rgba(122,27,140,${0.5 * (1 - d / alcance)})`; // #7A1B8C
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      for (const n of nos) {
        const pulso = (Math.sin(t / 900 + n.p) + 1) / 2;
        const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.r * 6);
        g.addColorStop(0, `rgba(192,75,219,${0.35 + 0.25 * pulso})`);
        g.addColorStop(1, 'rgba(192,75,219,0)');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r * 6, 0, 6.283);
        ctx.fill();

        ctx.fillStyle = pulso > 0.9 ? '#F3D9FA' : '#C04BDB';
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, 6.283);
        ctx.fill();

        if (!reduzir) {
          n.x += n.vx;
          n.y += n.vy;
          if (n.x < 0 || n.x > w) n.vx *= -1;
          if (n.y < 0 || n.y > h) n.vy *= -1;
        }
      }
    }

    requestAnimationFrame(quadro);
  }

  window.addEventListener('resize', iniciar);
  window.addEventListener('load', iniciar);

  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', iniciar);
  }

  iniciar();
  requestAnimationFrame(quadro);
})();
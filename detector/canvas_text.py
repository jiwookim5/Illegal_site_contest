"""Observe bounded 2D text draws and require unchanged final bitmap evidence."""
CANVAS_HOOK = r"""
(() => {
  const proto = window.CanvasRenderingContext2D?.prototype;
  if (!proto) return;
  const records = new WeakMap(), clipped = new WeakSet();
  const read = proto.getImageData;
  const snapshot = ctx => {
    const c = ctx.canvas;
    if (!c.width || !c.height || c.width * c.height > 524288) return null;
    try { return read.call(ctx, 0, 0, c.width, c.height).data; } catch (_) { return null; }
  };
  const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => v === b[i]);
  const clip = proto.clip;
  proto.clip = function (...args) { const value = clip.apply(this, args); clipped.add(this); return value; };
  for (const method of ['fillText', 'strokeText']) {
    const native = proto[method];
    proto[method] = function (...args) {
      let before = null, text = null;
      try {
        const tr = this.getTransform(), t = String(args[0]), x = Number(args[1]), y = Number(args[2]);
        const m = this.measureText(t), width = m.width;
        if (!clipped.has(this) && t.length <= 1000 && this.globalAlpha > 0.05 &&
            this.globalCompositeOperation === 'source-over' && this.textBaseline === 'alphabetic' &&
            ['left','start'].includes(this.textAlign) && this.direction !== 'rtl' &&
            tr.a === 1 && tr.b === 0 && tr.c === 0 && tr.d === 1 && tr.e === 0 && tr.f === 0 &&
            (args.length < 4 || Number(args[3]) >= width) &&
            x - m.actualBoundingBoxLeft >= 0 && x + m.actualBoundingBoxRight <= this.canvas.width &&
            y - m.actualBoundingBoxAscent >= 0 && y + m.actualBoundingBoxDescent <= this.canvas.height) {
          before = snapshot(this); text = t;
        }
      } catch (_) {}
      const value = native.apply(this, args);
      if (before && text) {
        const after = snapshot(this);
        if (after && !same(before, after)) {
          const previous = records.get(this.canvas);
          const texts = previous && same(previous.pixels, before) ? previous.texts : [];
          if (texts.length < 10) texts.push(text);
          records.set(this.canvas, { ctx: this, pixels: after, texts,
                                      width: this.canvas.width, height: this.canvas.height });
        }
      }
      return value;
    };
  }
  window.__hwonhiCanvasText = canvas => {
    const r = records.get(canvas);
    if (!r || r.width !== canvas.width || r.height !== canvas.height || !same(r.pixels, snapshot(r.ctx))) return '';
    return r.texts.join(' ');
  };
})();
"""

import { useEffect, useRef } from 'react';

function computePhase(time: number, epoch: number, period: number): number {
  return (((time - epoch + 0.5 * period) % period) + period) % period / period - 0.5;
}

const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export default function FoldingPlot({
  time,
  flux,
  periodDays,
  epochDays,
  durationHours,
  accent,
  label,
}: {
  time: number[];
  flux: number[];
  periodDays: number;
  epochDays: number;
  durationHours: number;
  accent: string;
  label: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || time.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const sweepDuration = reduceMotion ? 0 : 950;
    const start = performance.now();

    const phase = time.map((t) => computePhase(t, epochDays, periodDays));
    const timeMin = Math.min(...time);
    const timeMax = Math.max(...time);
    const fluxMin = Math.min(...flux);
    const fluxMax = Math.max(...flux);
    const fluxSpan = Math.max(fluxMax - fluxMin, 0.0001);
    const halfWidth = durationHours / 24 / periodDays / 2;

    let raf = 0;
    let lastCanvasWidth = 0;
    let lastCanvasHeight = 0;
    const render = (now: number) => {
      const box = canvas.getBoundingClientRect();
      const scale = window.devicePixelRatio || 1;
      const targetWidth = Math.max(1, box.width * scale);
      const targetHeight = Math.max(1, box.height * scale);
      if (targetWidth !== lastCanvasWidth || targetHeight !== lastCanvasHeight) {
        canvas.width = targetWidth;
        canvas.height = targetHeight;
        lastCanvasWidth = targetWidth;
        lastCanvasHeight = targetHeight;
      }
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      const width = box.width;
      const height = box.height;
      const pad = { left: 48, right: 16, top: 18, bottom: 34 };

      const elapsed = now - start;
      const progress = sweepDuration === 0 ? 1 : Math.min(1, elapsed / sweepDuration);
      const eased = easeInOutCubic(progress);

      const toY = (v: number) =>
        pad.top + ((fluxMax + fluxSpan * 0.08 - v) / (fluxSpan * 1.16)) * (height - pad.top - pad.bottom);
      const toXTime = (t: number) =>
        pad.left + ((t - timeMin) / (timeMax - timeMin || 1)) * (width - pad.left - pad.right);
      const toXPhase = (p: number) => pad.left + (p + 0.5) * (width - pad.left - pad.right);

      ctx.clearRect(0, 0, width, height);

      ctx.strokeStyle = 'rgba(210, 200, 255, .12)';
      ctx.fillStyle = '#8f83bb';
      ctx.font = '10px ui-monospace, monospace';
      for (let i = 0; i <= 4; i += 1) {
        const y = pad.top + ((height - pad.top - pad.bottom) / 4) * i;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(width - pad.right, y);
        ctx.stroke();
      }
      ctx.fillText(fluxMin.toFixed(4), 4, height - pad.bottom + 2);
      ctx.fillText(fluxMax.toFixed(4), 4, pad.top + 4);
      const showFolded = progress > 0.6;
      ctx.fillText(showFolded ? '-0.50' : timeMin.toFixed(2), pad.left, height - 10);
      ctx.fillText(showFolded ? '0.50' : timeMax.toFixed(2), width - pad.right - 34, height - 10);

      if (progress > 0.55) {
        const glowIn = Math.min(1, (progress - 0.55) / 0.45);
        const hx0 = toXPhase(-halfWidth);
        const hx1 = toXPhase(halfWidth);
        const pulse = reduceMotion ? 0.16 : 0.14 + Math.sin(now / 450) * 0.07;
        ctx.fillStyle = accent;
        ctx.globalAlpha = Math.max(0.04, pulse) * glowIn;
        ctx.fillRect(hx0, pad.top, Math.max(1, hx1 - hx0), height - pad.top - pad.bottom);
        ctx.globalAlpha = 1;
      }

      ctx.fillStyle = accent;
      ctx.globalAlpha = 0.55;
      for (let i = 0; i < time.length; i += 1) {
        const rawX = toXTime(time[i]);
        const foldedX = toXPhase(phase[i]);
        const x = rawX + (foldedX - rawX) * eased;
        const y = toY(flux[i]);
        ctx.fillRect(x - 0.8, y - 0.8, 1.6, 1.6);
      }
      ctx.globalAlpha = 1;

      if (progress < 1 || !reduceMotion) raf = requestAnimationFrame(render);
    };
    raf = requestAnimationFrame(render);

    const resizeObserver = new ResizeObserver(() => render(performance.now()));
    resizeObserver.observe(canvas);
    return () => {
      cancelAnimationFrame(raf);
      resizeObserver.disconnect();
    };
  }, [time, flux, periodDays, epochDays, durationHours, accent]);

  return <canvas ref={canvasRef} className="plot" role="img" aria-label={label} />;
}

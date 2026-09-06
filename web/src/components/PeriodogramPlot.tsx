import { useEffect, useRef } from 'react';

export default function PeriodogramPlot({
  period,
  power,
  markerPeriod,
  accent = '#9b8cff',
}: {
  period: number[];
  power: number[];
  markerPeriod?: number;
  accent?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || period.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const duration = reduceMotion ? 0 : 550;
    const start = performance.now();

    const periodMin = Math.min(...period);
    const periodMax = Math.max(...period);
    const powerMin = Math.min(...power);
    const powerMax = Math.max(...power);
    const powerSpan = Math.max(powerMax - powerMin, 1e-12);

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

      const toX = (value: number) =>
        pad.left + ((value - periodMin) / (periodMax - periodMin || 1)) * (width - pad.left - pad.right);
      const toY = (value: number) =>
        pad.top + ((powerMax + powerSpan * 0.08 - value) / (powerSpan * 1.16)) * (height - pad.top - pad.bottom);

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
      ctx.fillText('0', 4, height - pad.bottom + 2);
      ctx.fillText(powerMax.toExponential(1), 4, pad.top + 4);
      ctx.fillText(`${periodMin.toFixed(2)}d`, pad.left, height - 10);
      ctx.fillText(`${periodMax.toFixed(2)}d`, width - pad.right - 40, height - 10);

      const elapsed = now - start;
      const progress = duration === 0 ? 1 : Math.min(1, elapsed / duration);
      const count = Math.max(2, Math.round(period.length * progress));

      ctx.strokeStyle = accent;
      ctx.lineWidth = 1.1;
      ctx.beginPath();
      for (let i = 0; i < count; i += 1) {
        const x = toX(period[i]);
        const y = toY(power[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.fillStyle = accent;
      ctx.globalAlpha = 0.5;
      for (let i = 0; i < count; i += 2) {
        ctx.fillRect(toX(period[i]) - 0.6, toY(power[i]) - 0.6, 1.2, 1.2);
      }
      ctx.globalAlpha = 1;

      if (
        markerPeriod !== undefined &&
        markerPeriod >= periodMin &&
        markerPeriod <= periodMax &&
        progress > 0.5
      ) {
        const markerAlpha = Math.min(1, (progress - 0.5) / 0.5);
        const mx = toX(markerPeriod);
        ctx.strokeStyle = '#ffffff';
        ctx.globalAlpha = 0.6 * markerAlpha;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(mx, pad.top);
        ctx.lineTo(mx, height - pad.bottom);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
        ctx.fillStyle = '#ffffff';
        ctx.font = '9px ui-monospace, monospace';
        ctx.fillText(`${markerPeriod.toFixed(3)}d`, mx + 4, pad.top + 12);
      }

      if (progress < 1) raf = requestAnimationFrame(render);
    };
    raf = requestAnimationFrame(render);

    const resizeObserver = new ResizeObserver(() => render(performance.now()));
    resizeObserver.observe(canvas);
    return () => {
      cancelAnimationFrame(raf);
      resizeObserver.disconnect();
    };
  }, [period, power, markerPeriod, accent]);

  return <canvas ref={canvasRef} className="plot" role="img" aria-label="BLS periodogram" />;
}

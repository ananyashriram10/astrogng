import { useEffect, useRef } from 'react';

/** Draws one of the fixed-length binned arrays that get fed straight into the CNN. */
export default function ModelInputView({
  values,
  accent,
  label,
}: {
  values: number[];
  accent: string;
  label: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || values.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const render = () => {
      const box = canvas.getBoundingClientRect();
      if (box.width < 10 || box.height < 10) return;
      const scale = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, box.width * scale);
      canvas.height = Math.max(1, box.height * scale);
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      const width = box.width;
      const height = box.height;
      const pad = 8;

      const min = Math.min(...values);
      const max = Math.max(...values);
      const span = Math.max(max - min, 1e-9);
      const toX = (i: number) => pad + (i / (values.length - 1 || 1)) * (width - pad * 2);
      const toY = (v: number) => pad + ((max - v) / span) * (height - pad * 2);

      ctx.clearRect(0, 0, width, height);

      // one faint bar per bin, so it reads as "an array of numbers", not a curve
      ctx.fillStyle = accent;
      const barWidth = Math.max(1, (width - pad * 2) / values.length - 0.6);
      values.forEach((value, i) => {
        const y = toY(value);
        ctx.globalAlpha = 0.28;
        ctx.fillRect(toX(i) - barWidth / 2, y, barWidth, height - pad - y);
      });
      ctx.globalAlpha = 1;

      ctx.strokeStyle = accent;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      values.forEach((value, i) => {
        const x = toX(i);
        const y = toY(value);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    };

    render();
    const observer = new ResizeObserver(render);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [values, accent]);

  return <canvas ref={canvasRef} className="model-input-canvas" role="img" aria-label={label} />;
}

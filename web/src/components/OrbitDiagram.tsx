import { useEffect, useRef } from 'react';
import type { Candidate } from '../api';

const DEFAULT_GOOD_RGB = '139,233,201';
const DEFAULT_RISK_RGB = '255,157,138';

type HitTarget = { x: number; y: number; r: number; index: number };

export default function OrbitDiagram({
  candidates,
  selectedIndex,
  onSelect,
  goodRgb = DEFAULT_GOOD_RGB,
  riskRgb = DEFAULT_RISK_RGB,
}: {
  candidates: Candidate[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  /** "r,g,b" triplets, so callers can retheme without touching the draw logic. */
  goodRgb?: string;
  riskRgb?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const anglesRef = useRef<number[]>([]);
  const hitsRef = useRef<HitTarget[]>([]);

  useEffect(() => {
    anglesRef.current = candidates.map(() => Math.random() * Math.PI * 2);
  }, [candidates]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const rankByPeriod = [...candidates.keys()].sort(
      (a, b) => candidates[a].period_days - candidates[b].period_days,
    );
    const rankOf = new Map(rankByPeriod.map((originalIndex, rank) => [originalIndex, rank]));

    let raf = 0;
    let last = performance.now();
    let lastCanvasWidth = 0;
    let lastCanvasHeight = 0;
    const tilt = 0.44;

    const render = (now: number) => {
      const delta = Math.min(0.05, (now - last) / 1000);
      last = now;
      const box = canvas.getBoundingClientRect();
      if (box.width < 40 || box.height < 40) {
        raf = requestAnimationFrame(render);
        return;
      }
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
      const w = box.width;
      const h = box.height;
      const cx = w / 2;
      const cy = h / 2;
      const minRadius = 20;
      const maxRadius = Math.max(Math.min(w, h) / 2 - 16, minRadius);
      const ringGap = candidates.length > 1 ? (maxRadius - minRadius) / (candidates.length - 1) : 0;

      ctx.clearRect(0, 0, w, h);

      candidates.forEach((_, i) => {
        const rank = rankOf.get(i) ?? 0;
        const r = minRadius + rank * ringGap;
        const isSelected = i === selectedIndex;
        ctx.beginPath();
        ctx.ellipse(cx, cy, r, r * tilt, 0, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? 'rgba(255,255,255,.5)' : 'rgba(255,255,255,.13)';
        ctx.lineWidth = isSelected ? 1.5 : 1;
        ctx.stroke();
      });

      const starGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 13);
      starGlow.addColorStop(0, 'rgba(255,246,232,.9)');
      starGlow.addColorStop(1, 'rgba(255,246,232,0)');
      ctx.fillStyle = starGlow;
      ctx.beginPath();
      ctx.arc(cx, cy, 13, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#fff6e8';
      ctx.beginPath();
      ctx.arc(cx, cy, 5, 0, Math.PI * 2);
      ctx.fill();

      const hits: HitTarget[] = [];
      candidates.forEach((c, i) => {
        const rank = rankOf.get(i) ?? 0;
        const r = minRadius + rank * ringGap;
        if (!reduceMotion) {
          anglesRef.current[i] = (anglesRef.current[i] ?? 0) + delta * (0.55 / Math.sqrt(c.period_days));
        }
        const angle = anglesRef.current[i] ?? 0;
        const x = cx + Math.cos(angle) * r;
        const y = cy + Math.sin(angle) * r * tilt;
        const isSelected = i === selectedIndex;
        const rgb = c.disposition === 'planet-like' ? goodRgb : riskRgb;
        const radius = isSelected ? 7 : 4.5;

        if (isSelected) {
          ctx.beginPath();
          ctx.arc(x, y, radius + 5, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${rgb},0.22)`;
          ctx.fill();
        }
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${rgb},1)`;
        ctx.fill();

        hits.push({ x, y, r: radius + 11, index: i });
      });
      hitsRef.current = hits;

      raf = requestAnimationFrame(render);
    };
    raf = requestAnimationFrame(render);
    return () => cancelAnimationFrame(raf);
  }, [candidates, selectedIndex, goodRgb, riskRgb]);

  const handleClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    for (const hit of hitsRef.current) {
      if (Math.hypot(hit.x - x, hit.y - y) <= hit.r) {
        onSelect(hit.index);
        return;
      }
    }
  };

  return (
    <canvas
      ref={canvasRef}
      className="orbit-diagram"
      onClick={handleClick}
      role="img"
      aria-label="System orbit diagram, click a world to select it"
    />
  );
}

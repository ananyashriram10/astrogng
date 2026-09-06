import { useEffect, useRef } from 'react';

type Star = {
  x: number;
  y: number;
  radius: number;
  baseAlpha: number;
  twinkleSpeed: number;
  twinklePhase: number;
  parallax: number;
};

const STAR_COUNT = 220;

export default function Starfield() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let stars: Star[] = [];
    let width = 0;
    let height = 0;
    let pointer = { x: 0, y: 0 };
    let frame = 0;

    const seed = (w: number, h: number) => {
      stars = Array.from({ length: STAR_COUNT }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        radius: Math.random() * 1.3 + 0.3,
        baseAlpha: Math.random() * 0.6 + 0.25,
        twinkleSpeed: Math.random() * 0.015 + 0.004,
        twinklePhase: Math.random() * Math.PI * 2,
        parallax: Math.random() * 0.5 + 0.15,
      }));
    };

    const resize = () => {
      const scale = window.devicePixelRatio || 1;
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width * scale;
      canvas.height = height * scale;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      seed(width, height);
    };

    const draw = () => {
      ctx.clearRect(0, 0, width, height);
      const dx = (pointer.x - width / 2) / width;
      const dy = (pointer.y - height / 2) / height;
      for (const star of stars) {
        const twinkle = reduceMotion
          ? star.baseAlpha
          : star.baseAlpha + Math.sin(frame * star.twinkleSpeed + star.twinklePhase) * 0.28;
        const px = star.x - dx * star.parallax * 22;
        const py = star.y - dy * star.parallax * 22;
        ctx.beginPath();
        ctx.globalAlpha = Math.max(0, Math.min(1, twinkle));
        ctx.fillStyle = '#ffffff';
        ctx.arc(px, py, star.radius, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      frame += 1;
      if (!reduceMotion) requestAnimationFrame(draw);
    };

    const handlePointer = (event: PointerEvent) => {
      pointer = { x: event.clientX, y: event.clientY };
    };

    resize();
    draw();
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', handlePointer);
    return () => {
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', handlePointer);
    };
  }, []);

  return <canvas ref={canvasRef} className="starfield" aria-hidden="true" />;
}

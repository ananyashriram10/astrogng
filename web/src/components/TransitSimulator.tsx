import { useMemo, useState } from 'react';

const SUN_RADIUS_EARTHS = 109.076;

const PRESETS = [
  { label: 'Earth', radiusEarth: 1, periodDays: 365 },
  { label: 'Neptune', radiusEarth: 3.9, periodDays: 60 },
  { label: 'Jupiter', radiusEarth: 11.2, periodDays: 12 },
  { label: 'Hot Jupiter', radiusEarth: 11.2, periodDays: 3 },
];

/** Sliders for planet size and orbital period, wired to the real transit equations. */
export default function TransitSimulator() {
  const [radiusEarth, setRadiusEarth] = useState(3.9);
  const [periodDays, setPeriodDays] = useState(60);
  const [starRadiusSolar, setStarRadiusSolar] = useState(1);

  const model = useMemo(() => {
    const ratio = radiusEarth / (starRadiusSolar * SUN_RADIUS_EARTHS);
    const depth = ratio * ratio;
    const depthPpm = depth * 1_000_000;
    // a^3 = M * P^2 in solar units; assume a main-sequence M ≈ R for this toy.
    const axisAu = Math.cbrt(starRadiusSolar * (periodDays / 365.25) ** 2);
    // Central transit across a circular orbit: T ≈ (P/π)(R*/a).
    const starRadiusAu = starRadiusSolar * 0.00465047;
    const durationHours = (periodDays / Math.PI) * (starRadiusAu / axisAu) * 24;
    // Kepler-class photometry: ~30 ppm scatter per 6-hour window on a bright star.
    const transitsPerYear = 365.25 / periodDays;
    const snr = (depthPpm / 30) * Math.sqrt(Math.max(transitsPerYear, 0.2));
    return { depthPpm, axisAu, durationHours, snr, ratio };
  }, [radiusEarth, periodDays, starRadiusSolar]);

  // Draw the dip at a fixed visual scale so the slider's effect is legible:
  // the deepest case (Jupiter across the Sun, ~1%) fills the plot box.
  const dipFraction = Math.min(1, model.depthPpm / 12000);
  const dipY = 34 + dipFraction * 40;
  const halfWidth = Math.max(4, Math.min(34, model.durationHours * 1.1));
  const planetPx = Math.max(1.4, model.ratio * 34);

  const detectable = model.snr >= 7.1;

  return (
    <div className="sim">
      <div className="sim-stage">
        <svg viewBox="0 0 260 150" role="img" aria-label="Simulated transit">
          <defs>
            <radialGradient id="simStar" cx="50%" cy="50%">
              <stop offset="0%" stopColor="#fff6e8" />
              <stop offset="65%" stopColor="#ffdca8" />
              <stop offset="100%" stopColor="#ffb765" stopOpacity="0.2" />
            </radialGradient>
          </defs>
          <circle cx="70" cy="42" r="44" fill="url(#simStar)" opacity="0.25" />
          <circle cx="70" cy="42" r="34" fill="url(#simStar)" />
          <circle cx="70" cy="42" r={planetPx} fill="#0a0716" />

          <line x1="0" y1="34" x2="260" y2="34" stroke="rgba(255,255,255,.12)" strokeWidth="0.7" />
          <path
            d={`M 0,34 L ${130 - halfWidth},34 L ${130 - halfWidth + 4},${dipY} L ${
              130 + halfWidth - 4
            },${dipY} L ${130 + halfWidth},34 L 260,34`}
            fill="none"
            stroke={detectable ? '#8be9c9' : '#ff9d8a'}
            strokeWidth="1.8"
            transform="translate(0, 62)"
          />
          <text x="4" y="140" className="sim-axis">
            brightness over time
          </text>
        </svg>
      </div>

      <div className="sim-controls">
        <label className="sim-slider">
          <span>
            Planet radius <b>{radiusEarth.toFixed(1)} R⊕</b>
          </span>
          <input
            type="range"
            min={0.5}
            max={15}
            step={0.1}
            value={radiusEarth}
            onChange={(e) => setRadiusEarth(Number(e.target.value))}
          />
        </label>
        <label className="sim-slider">
          <span>
            Orbital period <b>{periodDays < 10 ? periodDays.toFixed(1) : Math.round(periodDays)} days</b>
          </span>
          <input
            type="range"
            min={1}
            max={400}
            step={1}
            value={periodDays}
            onChange={(e) => setPeriodDays(Number(e.target.value))}
          />
        </label>
        <label className="sim-slider">
          <span>
            Host star radius <b>{starRadiusSolar.toFixed(2)} R☉</b>
          </span>
          <input
            type="range"
            min={0.1}
            max={2.5}
            step={0.05}
            value={starRadiusSolar}
            onChange={(e) => setStarRadiusSolar(Number(e.target.value))}
          />
        </label>

        <div className="sim-presets">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              onClick={() => {
                setRadiusEarth(preset.radiusEarth);
                setPeriodDays(preset.periodDays);
                setStarRadiusSolar(1);
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <div className="sim-readout">
        <div>
          <span>TRANSIT DEPTH</span>
          <strong>{Math.round(model.depthPpm).toLocaleString()} ppm</strong>
          <small>{(model.depthPpm / 10000).toFixed(3)}% of the star&rsquo;s light</small>
        </div>
        <div>
          <span>ORBITAL DISTANCE</span>
          <strong>{model.axisAu.toFixed(3)} AU</strong>
          <small>Kepler&rsquo;s third law</small>
        </div>
        <div>
          <span>TRANSIT LASTS</span>
          <strong>{model.durationHours.toFixed(1)} h</strong>
          <small>central crossing</small>
        </div>
        <div>
          <span>SIGNAL / NOISE</span>
          <strong className={detectable ? 'good' : 'risk'}>{model.snr.toFixed(1)}</strong>
          <small>after one year of staring</small>
        </div>
      </div>

      <p className={`sim-verdict ${detectable ? 'ok' : 'no'}`}>
        {detectable
          ? 'Detectable — this signal would stand clear of the noise within a year of observing.'
          : 'Too faint — this dip would still be buried in the noise after a year. Make the planet bigger, the star smaller, or the orbit tighter.'}
      </p>
    </div>
  );
}

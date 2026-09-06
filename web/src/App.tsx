import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ApiError,
  analyzeArchiveTargetStreamed,
  fetchCandidates,
  fetchTargets,
  type AnalysisResult,
  type Candidate,
  type ProgressEvent,
  type TargetSummary,
} from './api';
import Starfield from './components/Starfield';
import Landing from './components/Landing';
import Explainer from './components/Explainer';
import { AnalysisSkeleton } from './components/Skeleton';
import FoldingPlot from './components/FoldingPlot';
import OrbitDiagram from './components/OrbitDiagram';
import PeriodogramPlot from './components/PeriodogramPlot';
import ModelInputView from './components/ModelInputView';
import { useCountUp } from './hooks/useCountUp';

type SourceMode = 'demo' | 'live' | 'info';
type View = 'landing' | 'app';

function AnimatedNumber({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const animated = useCountUp(value);
  return <>{animated.toFixed(decimals)}</>;
}

function Plot({
  points,
  accent,
  label,
  highlight,
}: {
  points: { x: number; y: number }[];
  accent: string;
  label: string;
  highlight?: { x0: number; x1: number };
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || points.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const revealDuration = reduceMotion ? 0 : 650;
    const startTime = performance.now();
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
      const xMin = Math.min(...points.map((point) => point.x));
      const xMax = Math.max(...points.map((point) => point.x));
      const values = points.map((point) => point.y);
      const yMin = Math.min(...values);
      const yMax = Math.max(...values);
      const span = Math.max(yMax - yMin, 0.0001);
      const toX = (value: number) =>
        pad.left + ((value - xMin) / (xMax - xMin || 1)) * (width - pad.left - pad.right);
      const toY = (value: number) =>
        pad.top + ((yMax + span * 0.08 - value) / (span * 1.16)) * (height - pad.top - pad.bottom);

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
      ctx.fillText(yMin.toFixed(4), 4, height - pad.bottom + 2);
      ctx.fillText(yMax.toFixed(4), 4, pad.top + 4);
      ctx.fillText(xMin.toFixed(2), pad.left, height - 10);
      ctx.fillText(xMax.toFixed(2), width - pad.right - 30, height - 10);

      if (highlight) {
        const hx0 = toX(highlight.x0);
        const hx1 = toX(highlight.x1);
        const pulse = reduceMotion ? 0.16 : 0.14 + Math.sin(now / 450) * 0.07;
        ctx.fillStyle = accent;
        ctx.globalAlpha = Math.max(0.05, pulse);
        ctx.fillRect(Math.min(hx0, hx1), pad.top, Math.max(1, Math.abs(hx1 - hx0)), height - pad.top - pad.bottom);
        ctx.globalAlpha = 1;
      }

      const elapsed = now - startTime;
      const progress = revealDuration === 0 ? 1 : Math.min(1, elapsed / revealDuration);
      const count = Math.max(2, Math.round(points.length * progress));
      const visible = points.slice(0, count);

      ctx.strokeStyle = accent;
      ctx.lineWidth = 1.25;
      ctx.beginPath();
      visible.forEach((point, index) => {
        const x = toX(point.x);
        const y = toY(point.y);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.fillStyle = accent;
      visible.forEach((point, index) => {
        if (index % 2) return;
        ctx.globalAlpha = 0.58;
        ctx.fillRect(toX(point.x) - 0.7, toY(point.y) - 0.7, 1.4, 1.4);
      });
      ctx.globalAlpha = 1;

      if (progress < 1 || highlight) {
        raf = requestAnimationFrame(render);
      }
    };
    raf = requestAnimationFrame(render);

    const resizeObserver = new ResizeObserver(() => render(performance.now()));
    resizeObserver.observe(canvas);
    return () => {
      cancelAnimationFrame(raf);
      resizeObserver.disconnect();
    };
  }, [points, accent, highlight?.x0, highlight?.x1]);

  return <canvas ref={canvasRef} className="plot" role="img" aria-label={label} />;
}

function MiniSignal({ candidate }: { candidate: Candidate }) {
  const points = useMemo(
    () => candidate.phase.map((x, i) => ({ x, y: candidate.folded_flux[i] })),
    [candidate],
  );
  if (points.length === 0) return <div className="mini-signal" aria-hidden="true" />;
  const min = Math.min(...points.map((p) => p.y));
  const max = Math.max(...points.map((p) => p.y));
  const stride = Math.max(1, Math.floor(points.length / 45));
  const sampled = points.filter((_, index) => index % stride === 0);
  return (
    <div className="mini-signal" aria-hidden="true">
      {sampled.map((point, index) => (
        <i
          key={index}
          style={{
            left: `${(index / Math.max(1, sampled.length - 1)) * 100}%`,
            bottom: `${((point.y - min) / (max - min || 1)) * 70 + 12}%`,
          }}
        />
      ))}
    </div>
  );
}

function ComparisonCard({
  candidate,
  isSelected,
  onSelect,
  goodColor,
  riskColor,
}: {
  candidate: Candidate;
  isSelected: boolean;
  onSelect: () => void;
  goodColor: string;
  riskColor: string;
}) {
  const points = useMemo(
    () => candidate.phase.map((x, i) => ({ x, y: candidate.folded_flux[i] })),
    [candidate],
  );
  const highlight = useMemo(() => {
    const halfWidth = candidate.duration_hours / 24 / candidate.period_days / 2;
    return { x0: -halfWidth, x1: halfWidth };
  }, [candidate]);
  const isGood = candidate.disposition === 'planet-like';
  const accent = isGood ? goodColor : riskColor;

  return (
    <button
      className={`compare-card ${isSelected ? 'selected' : ''}`}
      onClick={onSelect}
    >
      <div className="compare-card-head">
        <span>{candidate.candidate_id}</span>
        <b className={isGood ? 'good' : 'risk'}>{Math.round(candidate.confidence * 100)}%</b>
      </div>
      <Plot
        points={points}
        accent={accent}
        label={`Phase-folded signal for ${candidate.candidate_id}`}
        highlight={highlight}
      />
      <div className="compare-card-meta">
        <span>{candidate.period_days.toFixed(3)} d</span>
        <span>{Math.round(candidate.depth_ppm).toLocaleString()} ppm</span>
        <span>{candidate.num_transits_observed} events</span>
      </div>
    </button>
  );
}

export default function App() {
  const [view, setView] = useState<View>('landing');
  const [sourceMode, setSourceMode] = useState<SourceMode>('demo');

  const [targets, setTargets] = useState<TargetSummary[]>([]);
  const [targetsError, setTargetsError] = useState<string | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<string | null>(null);

  const [demoResult, setDemoResult] = useState<AnalysisResult | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);

  const [liveTarget, setLiveTarget] = useState('');
  const [liveMission, setLiveMission] = useState<'Kepler' | 'TESS'>('Kepler');
  const [liveMaxFiles, setLiveMaxFiles] = useState(4);
  const [liveUsePeriodHint, setLiveUsePeriodHint] = useState(true);
  const [liveResult, setLiveResult] = useState<AnalysisResult | null>(null);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [liveProgress, setLiveProgress] = useState<ProgressEvent[]>([]);

  const [fluxView, setFluxView] = useState<'raw' | 'detrended'>('detrended');
  const [candidateIndex, setCandidateIndex] = useState(0);

  useEffect(() => {
    fetchTargets()
      .then((list) => {
        setTargets(list);
        if (list.length > 0) setSelectedTarget(list[0].target);
      })
      .catch((err: unknown) => {
        setTargetsError(err instanceof ApiError ? err.message : 'Failed to load targets.');
      });
  }, []);

  useEffect(() => {
    if (sourceMode !== 'demo' || !selectedTarget) return;
    setDemoLoading(true);
    setDemoError(null);
    fetchCandidates(selectedTarget)
      .then((result) => {
        setDemoResult(result);
        setCandidateIndex(0);
      })
      .catch((err: unknown) => {
        setDemoError(err instanceof ApiError ? err.message : 'Failed to load this target.');
        setDemoResult(null);
      })
      .finally(() => setDemoLoading(false));
  }, [sourceMode, selectedTarget]);

  const handleAnalyzeLive = async () => {
    if (!liveTarget.trim()) {
      setLiveError('Enter a KOI, KIC, or object name first.');
      return;
    }
    setLiveLoading(true);
    setLiveError(null);
    setLiveResult(null);
    setLiveProgress([]);
    try {
      const { promise } = analyzeArchiveTargetStreamed(
        {
          target: liveTarget.trim(),
          mission: liveMission,
          maxFiles: liveMaxFiles,
          usePeriodHint: liveUsePeriodHint,
        },
        (event) => setLiveProgress((log) => [...log, event]),
      );
      const result = await promise;
      setLiveResult(result);
      setCandidateIndex(0);
    } catch (err) {
      setLiveError(err instanceof ApiError ? err.message : 'Analysis failed.');
    } finally {
      setLiveLoading(false);
    }
  };

  const result = sourceMode === 'live' ? liveResult : sourceMode === 'demo' ? demoResult : null;
  const loading = sourceMode === 'live' ? liveLoading : sourceMode === 'demo' ? demoLoading : false;
  const error = sourceMode === 'live' ? liveError : sourceMode === 'demo' ? demoError : null;
  const candidate = result?.candidates[Math.min(candidateIndex, Math.max(result.candidates.length - 1, 0))];

  // Each data-source mode gets its own time-of-day theme, scoped via a class
  // on <main>: demo catalog is sunset (magenta/gold), live lookup is sunrise
  // (fiery red/orange/yellow), and the primer is a bright sunny sky (blue/gold).
  const isSunset = sourceMode === 'demo';
  const isSunrise = sourceMode === 'live';
  const isSky = sourceMode === 'info';
  const themeClass = isSunset ? 'theme-sunset' : isSunrise ? 'theme-sunrise' : isSky ? 'theme-sky' : '';
  const accentPrimary = isSunset ? '#ff8a5c' : isSunrise ? '#ff6a2e' : isSky ? '#2f9fe0' : '#9b8cff';
  const accentGood = isSunset ? '#e8c15a' : isSunrise ? '#ffcc4d' : isSky ? '#3fae6a' : '#8be9c9';
  const accentRisk = isSunset ? '#ff6f5c' : isSunrise ? '#ff4d3d' : isSky ? '#e0523d' : '#ff9d8a';

  const rawPoints = useMemo(() => {
    if (!result) return [];
    return result.raw_light_curve.time.map((x, i) => ({ x, y: result.raw_light_curve.flux[i] }));
  }, [result]);
  const detrendedPoints = useMemo(() => {
    if (!result) return [];
    return result.detrended_light_curve.time.map((x, i) => ({
      x,
      y: result.detrended_light_curve.flux[i],
    }));
  }, [result]);
  const [foldReplayTick, setFoldReplayTick] = useState(0);

  const bestConfidence = result ? Math.max(0, ...result.candidates.map((c) => c.confidence)) : 0;

  const catalogPeriod = result?.target_metadata?.catalog_period_days ?? null;
  const candidatePeriod = candidate?.period_days ?? null;
  const periodAgreement = useMemo(() => {
    if (catalogPeriod === null || candidatePeriod === null) {
      return { label: '', className: '' };
    }
    const offBy = Math.abs(candidatePeriod - catalogPeriod) / catalogPeriod;
    if (offBy <= 0.01) return { label: '✓ match', className: 'good' };
    const ratio = candidatePeriod / catalogPeriod;
    const harmonics: [number, string][] = [
      [2, '2× harmonic'],
      [0.5, '½× harmonic'],
      [3, '3× harmonic'],
      [1 / 3, '⅓× harmonic'],
    ];
    for (const [factor, name] of harmonics) {
      if (Math.abs(ratio - factor) / factor <= 0.02) {
        return { label: name, className: 'risk' };
      }
    }
    return {
      label: `${(offBy * 100).toFixed(offBy < 0.1 ? 1 : 0)}% off`,
      className: offBy <= 0.05 ? '' : 'risk',
    };
  }, [catalogPeriod, candidatePeriod]);

  if (view === 'landing') {
    return (
      <>
        <Starfield />
        <Landing
          targets={targets}
          targetsError={targetsError}
          onSelectTarget={(name) => {
            setSourceMode('demo');
            setSelectedTarget(name);
            setView('app');
          }}
          onEnterLive={() => {
            setSourceMode('live');
            setView('app');
          }}
          onLearnMore={() => {
            setSourceMode('info');
            setView('app');
          }}
        />
      </>
    );
  }

  return (
    <main className={themeClass}>
      {!isSunrise && !isSky && <Starfield />}
      {isSunset && <div className="sunset-wash" aria-hidden="true" />}
      {isSunrise && <div className="sunrise-wash" aria-hidden="true" />}
      {isSky && <div className="sky-wash" aria-hidden="true" />}
      <header className="topbar">
        <button className="brand" onClick={() => setView('landing')} aria-label="Back to orbit view">
          TARA
        </button>
      </header>

      {targetsError && (
        <div className="api-banner">
          {targetsError} Start the backend with{' '}
          <code>uvicorn exoplanet_lab.api:app --reload</code> in the project root.
        </div>
      )}

      <section className="hero" id="top">
        <div>
          <p className="eyebrow">
            EXOPLANET SIGNAL INTELLIGENCE{result ? ` / ${result.mission}` : ''}
          </p>
          <h1>
            Find the worlds
            <br />
            <em>hidden in starlight.</em>
          </h1>
          <p className="intro">
            A transit-detection workspace that turns subtle, repeating dips into explainable
            planet candidates.
          </p>
        </div>

        <div className="target-picker" aria-label="Select stellar target">
          <div className="mode-toggle" role="tablist" aria-label="Data source">
            <motion.button
              whileTap={{ scale: 0.96 }}
              className={sourceMode === 'demo' ? 'active' : ''}
              onClick={() => setSourceMode('demo')}
            >
              Demo catalog
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.96 }}
              className={sourceMode === 'live' ? 'active' : ''}
              onClick={() => setSourceMode('live')}
            >
              Live MAST lookup
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.96 }}
              className={sourceMode === 'info' ? 'active' : ''}
              onClick={() => setSourceMode('info')}
            >
              How it works
            </motion.button>
          </div>

          {sourceMode === 'info' ? (
            <p className="mode-info-hint">
              A plain-language primer on the physics and the pipeline, with an interactive
              simulator — no target selection needed here.
            </p>
          ) : sourceMode === 'demo' ? (
            <>
              <label>TARGET CATALOG</label>
              <div className="picker-grid">
                {targets.map((item) => (
                  <button
                    key={item.target}
                    className={item.target === selectedTarget ? 'active' : ''}
                    onClick={() => setSelectedTarget(item.target)}
                  >
                    <span>{item.target}</span>
                    <small>
                      {item.candidate_count} signal{item.candidate_count === 1 ? '' : 's'}
                    </small>
                  </button>
                ))}
                {targets.length === 0 && !targetsError && (
                  <span style={{ color: 'var(--muted)', fontSize: 12 }}>Loading catalog…</span>
                )}
              </div>
            </>
          ) : (
            <div className="live-form">
              <label>MAST TARGET</label>
              <input
                placeholder="KOI (K00752.01), KIC ID, or object name"
                value={liveTarget}
                onChange={(e) => setLiveTarget(e.target.value)}
              />
              <div className="live-form-row">
                <select value={liveMission} onChange={(e) => setLiveMission(e.target.value as 'Kepler' | 'TESS')}>
                  <option value="Kepler">Kepler</option>
                  <option value="TESS">TESS</option>
                </select>
                <input
                  type="number"
                  min={1}
                  max={15}
                  value={liveMaxFiles}
                  onChange={(e) => {
                    const parsed = Number(e.target.value);
                    if (Number.isFinite(parsed)) {
                      setLiveMaxFiles(Math.min(15, Math.max(1, Math.round(parsed))));
                    }
                  }}
                />
              </div>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={liveUsePeriodHint}
                  onChange={(e) => setLiveUsePeriodHint(e.target.checked)}
                />
                Use NASA KOI period hint (confirmation mode)
              </label>
              <motion.button whileTap={{ scale: 0.97 }} onClick={handleAnalyzeLive} disabled={liveLoading}>
                {liveLoading ? 'Fetching + analyzing…' : 'Fetch + analyze'}
              </motion.button>
              {liveProgress.length > 0 && (liveLoading || liveError) && (
                <ol className="progress-log">
                  {liveProgress.map((event, index) => {
                    const isLast = index === liveProgress.length - 1;
                    return (
                      <li
                        key={`${event.stage}-${index}`}
                        className={isLast && liveLoading ? 'active' : 'done'}
                      >
                        <i>{isLast && liveLoading ? '◌' : '✓'}</i>
                        <span>{event.detail || event.stage}</span>
                      </li>
                    );
                  })}
                </ol>
              )}
              {liveError && <p className="live-error">{liveError}</p>}
            </div>
          )}
        </div>
      </section>

      {sourceMode === 'info' && <Explainer embedded />}

      {loading && <AnalysisSkeleton />}
      {!loading && error && sourceMode === 'demo' && <div className="state-message">{error}</div>}
      {!loading && !result && sourceMode === 'live' && !error && (
        <div className="state-message">Enter a target above and run an analysis.</div>
      )}

      {/* No exit animation and no mode="wait" here on purpose: both make the
          old result linger until an animation completes, which never happens
          while the tab is backgrounded and rAF is paused. Results then swap
          instantly and only fade in. */}
      {result && candidate && (
          <motion.div
            key={`${sourceMode}-${result.target}`}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
          >
            <section className="stat-strip" aria-label="Analysis summary">
              <div>
                <span>ACTIVE TARGET</span>
                <strong>{result.target}</strong>
              </div>
              <div>
                <span>SIGNALS FOUND</span>
                <strong>{String(result.candidates.length).padStart(2, '0')}</strong>
              </div>
              <div>
                <span>SYSTEM</span>
                <strong>{result.is_multi_planet ? 'Multi-planet' : 'Single signal'}</strong>
              </div>
              <div>
                <span>TOP CONFIDENCE</span>
                <strong className={bestConfidence >= 0.5 ? 'good' : 'risk'}>
                  <AnimatedNumber value={bestConfidence * 100} />%
                </strong>
              </div>
            </section>

            <section className="workspace">
              <div className="panel curve-panel">
                <div className="panel-head">
                  <div>
                    <p>01 / LIGHT CURVE</p>
                    <h2>Stellar flux over time</h2>
                  </div>
                  <div className="segmented" role="group" aria-label="Flux view">
                    <motion.button
                      whileTap={{ scale: 0.95 }}
                      onClick={() => setFluxView('raw')}
                      className={fluxView === 'raw' ? 'active' : ''}
                    >
                      RAW
                    </motion.button>
                    <motion.button
                      whileTap={{ scale: 0.95 }}
                      onClick={() => setFluxView('detrended')}
                      className={fluxView === 'detrended' ? 'active' : ''}
                    >
                      DETRENDED
                    </motion.button>
                  </div>
                </div>
                <Plot
                  points={fluxView === 'raw' ? rawPoints : detrendedPoints}
                  accent={fluxView === 'raw' ? accentPrimary : (isSunset ? '#ffcf8a' : isSunrise ? '#ffe6a3' : '#ffffff')}
                  label={`${fluxView} light curve for ${result.target}`}
                />
                <div className="axis-caption">
                  <span>NORMALIZED FLUX</span>
                  <span>TIME →</span>
                </div>
              </div>

              <aside className="panel pipeline-panel">
                <div className="panel-head">
                  <div>
                    <p>PIPELINE STATUS</p>
                    <h2>Signal extraction</h2>
                  </div>
                  <span className="live">LIVE</span>
                </div>
                {[
                  'Quality filter',
                  'Robust detrending',
                  'Iterative BLS search',
                  'Feature extraction',
                  'Confidence ranking',
                ].map((step, index) => (
                  <div className="pipeline-step" key={step}>
                    <span>{String(index + 1).padStart(2, '0')}</span>
                    <b>{step}</b>
                    <i>✓</i>
                  </div>
                ))}
                <p className="source-note">{result.source}</p>
              </aside>
            </section>

            {result.periodogram && (
              <section className="diagnostics">
                <div className="panel curve-panel">
                  <div className="panel-head">
                    <div>
                      <p>SEARCH DIAGNOSTICS</p>
                      <h2>BLS periodogram</h2>
                    </div>
                  </div>
                  <PeriodogramPlot
                    period={result.periodogram.period}
                    power={result.periodogram.power}
                    markerPeriod={candidate.period_days}
                    accent={accentPrimary}
                  />
                  <div className="axis-caption">
                    <span>BLS POWER</span>
                    <span>PERIOD →</span>
                  </div>
                  <p className="source-note">
                    Power across the searched period range — the dashed line marks the selected
                    signal&rsquo;s period. Peaks show where the box-fitting search found repeating dips.
                  </p>
                </div>
              </section>
            )}

            <section className="candidates">
              <div className="section-title">
                <div>
                  <p>02 / CANDIDATE SIGNALS</p>
                  <h2>Repeated shadows, ranked</h2>
                </div>
                <p>Select a signal to inspect its phase-folded transit and vetting evidence.</p>
              </div>
              <div className="candidate-layout">
                <div className="candidate-side">
                  {result.candidates.length > 0 && (
                    <div className="panel orbit-diagram-panel">
                      <div className="orbit-diagram-head">
                        <span>SYSTEM MAP</span>
                        <span className="orbit-diagram-caption">not to scale</span>
                      </div>
                      <OrbitDiagram
                        candidates={result.candidates}
                        selectedIndex={candidateIndex}
                        onSelect={setCandidateIndex}
                        goodRgb={isSunset ? '232,193,90' : isSunrise ? '255,204,77' : undefined}
                        riskRgb={isSunset ? '255,111,92' : isSunrise ? '255,77,61' : undefined}
                      />
                    </div>
                  )}
                  <div className="candidate-list" role="list">
                  {result.candidates.map((item, index) => (
                    <button
                      role="listitem"
                      key={item.candidate_id}
                      className={index === candidateIndex ? 'selected' : ''}
                      onClick={() => setCandidateIndex(index)}
                    >
                      <span className="candidate-rank">{String(index + 1).padStart(2, '0')}</span>
                      <div>
                        <strong>{item.candidate_id}</strong>
                        <small>{item.period_days.toFixed(3)} day orbit</small>
                      </div>
                      <MiniSignal candidate={item} />
                      <b className={item.disposition === 'planet-like' ? 'good' : 'risk'}>
                        <AnimatedNumber value={item.confidence * 100} />%
                      </b>
                    </button>
                  ))}
                  </div>
                </div>

                <AnimatePresence>
                  <motion.article
                    key={candidate.candidate_id}
                    className="panel candidate-detail"
                    initial={{ opacity: 0, x: 12 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -12, position: 'absolute', pointerEvents: 'none' }}
                    transition={{ duration: 0.28, ease: 'easeOut' }}
                  >
                    <div className="detail-heading">
                      <div>
                        <span
                          className={`badge ${
                            candidate.disposition === 'planet-like' ? 'good-badge' : 'risk-badge'
                          }`}
                        >
                          {candidate.disposition}
                        </span>
                        <h3>{candidate.candidate_id}</h3>
                      </div>
                      <div className="confidence">
                        <span>CONFIDENCE</span>
                        <strong>
                          <AnimatedNumber value={candidate.confidence * 100} />
                          <small>%</small>
                        </strong>
                        {candidate.gbt_proba !== null && candidate.cnn_proba !== null && (
                          <p className="ensemble-breakdown">
                            GBT <AnimatedNumber value={candidate.gbt_proba * 100} />% · CNN{' '}
                            <AnimatedNumber value={candidate.cnn_proba * 100} />%
                          </p>
                        )}
                      </div>
                    </div>
                    {candidate.alias_reason && (
                      <p className="alias-notice">
                        <strong>Duplicate signal.</strong> {candidate.alias_reason}.
                      </p>
                    )}
                    <FoldingPlot
                      key={`${candidate.candidate_id}-${foldReplayTick}`}
                      time={result.detrended_light_curve.time}
                      flux={result.detrended_light_curve.flux}
                      periodDays={candidate.period_days}
                      epochDays={candidate.epoch_days}
                      durationHours={candidate.duration_hours}
                      accent={candidate.disposition === 'planet-like' ? accentGood : accentRisk}
                      label={`Phase-folded signal for ${candidate.candidate_id}`}
                    />
                    <div className="axis-caption">
                      <span>NORMALIZED FLUX</span>
                      <span>
                        TIMELINE → ORBITAL PHASE
                        <button
                          className="replay-fold"
                          onClick={() => setFoldReplayTick((t) => t + 1)}
                          title="Replay fold animation"
                          aria-label="Replay fold animation"
                        >
                          ↻
                        </button>
                      </span>
                    </div>
                    <div className="evidence-grid">
                      <div>
                        <span>PERIOD</span>
                        <strong>{candidate.period_days.toFixed(3)} d</strong>
                      </div>
                      <div>
                        <span>DURATION</span>
                        <strong>{candidate.duration_hours.toFixed(2)} h</strong>
                      </div>
                      <div>
                        <span>DEPTH</span>
                        <strong>{Math.round(candidate.depth_ppm).toLocaleString()} ppm</strong>
                      </div>
                      <div>
                        <span>SIGNAL / NOISE</span>
                        <strong>{candidate.snr.toFixed(1)}</strong>
                      </div>
                      <div>
                        <span>EVENTS</span>
                        <strong>{candidate.num_transits_observed}</strong>
                      </div>
                      <div>
                        <span>SHAPE</span>
                        <strong>{Math.round(candidate.transit_shape_symmetry * 100)}% symmetric</strong>
                      </div>
                    </div>

                    {(candidate.planet_radius_earth !== null ||
                      candidate.semi_major_axis_au !== null) && (
                      <div className="derived-strip">
                        <p className="derived-title">
                          WHAT THAT MEANS PHYSICALLY
                          {result.star?.radius_solar
                            ? ` · host star ${result.star.radius_solar.toFixed(2)} R☉`
                            : ''}
                        </p>
                        <div className="derived-grid">
                          {candidate.planet_radius_earth !== null && (
                            <div>
                              <span>PLANET RADIUS</span>
                              <strong>
                                <AnimatedNumber value={candidate.planet_radius_earth} decimals={2} /> R⊕
                              </strong>
                              {candidate.size_class && <small>{candidate.size_class}</small>}
                            </div>
                          )}
                          {candidate.semi_major_axis_au !== null && (
                            <div>
                              <span>ORBITAL DISTANCE</span>
                              <strong>
                                <AnimatedNumber value={candidate.semi_major_axis_au} decimals={3} /> AU
                              </strong>
                              <small>
                                {candidate.semi_major_axis_au < 1
                                  ? `${(candidate.semi_major_axis_au * 100).toFixed(0)}% of Earth's`
                                  : 'beyond Earth’s orbit'}
                              </small>
                            </div>
                          )}
                          {candidate.equilibrium_temp_k !== null && (
                            <div>
                              <span>EQUILIBRIUM TEMP</span>
                              <strong>
                                <AnimatedNumber value={candidate.equilibrium_temp_k} /> K
                              </strong>
                              <small>
                                {Math.round(candidate.equilibrium_temp_k - 273.15)}°C · assumes 0.3
                                albedo
                              </small>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </motion.article>
                </AnimatePresence>
              </div>

              {(candidate.global_view.length > 0 || catalogPeriod !== null) && (
                <div className="inspect-row">
                  {candidate.global_view.length > 0 && (
                    <div className="panel inspect-panel">
                      <p className="inspect-title">WHAT THE CNN ACTUALLY SEES</p>
                      <p className="inspect-note">
                        The network never reads your numbers — it reads these two binned arrays of
                        the folded curve.
                      </p>
                      <div className="model-input">
                        <span className="model-input-label">
                          GLOBAL VIEW · {candidate.global_view.length} bins · full orbit
                        </span>
                        <ModelInputView
                          values={candidate.global_view}
                          accent={accentPrimary}
                          label={`CNN global view for ${candidate.candidate_id}`}
                        />
                      </div>
                      <div className="model-input">
                        <span className="model-input-label">
                          LOCAL VIEW · {candidate.local_view.length} bins · zoomed on the dip
                        </span>
                        <ModelInputView
                          values={candidate.local_view}
                          accent={accentGood}
                          label={`CNN local view for ${candidate.candidate_id}`}
                        />
                      </div>
                    </div>
                  )}

                  {catalogPeriod !== null && (
                    <div className="panel inspect-panel">
                      <p className="inspect-title">VERSUS THE NASA CATALOG</p>
                      <p className="inspect-note">
                        What the archive already knows about{' '}
                        {result.target_metadata.kepoi_name ?? result.target}, next to what this
                        pipeline measured independently.
                      </p>
                      <table className="catalog-table">
                        <tbody>
                          <tr>
                            <th>Period</th>
                            <td>{catalogPeriod.toFixed(4)} d</td>
                            <td>{candidate.period_days.toFixed(4)} d</td>
                            <td className={periodAgreement.className}>
                              {periodAgreement.label}
                            </td>
                          </tr>
                          {result.target_metadata.catalog_depth_ppm != null && (
                            <tr>
                              <th>Depth</th>
                              <td>
                                {Math.round(
                                  result.target_metadata.catalog_depth_ppm,
                                ).toLocaleString()}{' '}
                                ppm
                              </td>
                              <td>{Math.round(candidate.depth_ppm).toLocaleString()} ppm</td>
                              <td />
                            </tr>
                          )}
                          {result.target_metadata.catalog_duration_hours != null && (
                            <tr>
                              <th>Duration</th>
                              <td>
                                {result.target_metadata.catalog_duration_hours.toFixed(2)} h
                              </td>
                              <td>{candidate.duration_hours.toFixed(2)} h</td>
                              <td />
                            </tr>
                          )}
                          <tr>
                            <th>Verdict</th>
                            <td>{result.target_metadata.catalog_disposition ?? '—'}</td>
                            <td className={candidate.disposition === 'planet-like' ? 'good' : 'risk'}>
                              {Math.round(candidate.confidence * 100)}% confidence
                            </td>
                            <td />
                          </tr>
                        </tbody>
                      </table>
                      <p className="catalog-legend">
                        <span>NASA</span>
                        <span>ours</span>
                      </p>
                    </div>
                  )}
                </div>
              )}

              {result.candidates.length > 1 && (
                <div className="compare-section">
                  <p className="compare-title">
                    COMPARE ALL SIGNALS — same axes, side by side
                  </p>
                  <div className="compare-grid">
                    {result.candidates.map((item, index) => (
                      <ComparisonCard
                        key={item.candidate_id}
                        candidate={item}
                        isSelected={index === candidateIndex}
                        onSelect={() => setCandidateIndex(index)}
                        goodColor={accentGood}
                        riskColor={accentRisk}
                      />
                    ))}
                  </div>
                </div>
              )}
            </section>

            <section className="explain">
              <div>
                <p>WHY THIS RANKING</p>
                <h2>Evidence you can defend.</h2>
              </div>
              <div className="explain-grid">
                <article>
                  <span>↙</span>
                  <h3>Repeated timing</h3>
                  <p>
                    {candidate.num_transits_observed} aligned events at a stable{' '}
                    {candidate.period_days.toFixed(2)}-day cadence.
                  </p>
                </article>
                <article>
                  <span>◇</span>
                  <h3>Transit geometry</h3>
                  <p>
                    {candidate.disposition === 'planet-like'
                      ? 'A shallow, symmetric shape supports a planetary transit.'
                      : 'The unusually deep or asymmetric event resembles an eclipsing stellar pair.'}
                  </p>
                </article>
                <article>
                  <span>≋</span>
                  <h3>False-positive checks</h3>
                  <p>
                    {candidate.disposition === 'planet-like'
                      ? `Odd/even depth difference of ${Math.round(candidate.odd_even_depth_diff_ppm)} ppm and no significant secondary eclipse.`
                      : `Secondary eclipse depth of ${Math.round(candidate.secondary_eclipse_depth_ppm)} ppm drives the confidence penalty.`}
                  </p>
                </article>
              </div>
            </section>
          </motion.div>
        )}

    </main>
  );
}

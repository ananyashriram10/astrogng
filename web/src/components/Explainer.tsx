import type { ReactNode } from 'react';
import TransitSimulator from './TransitSimulator';

function PhotoPlaceholder({
  label,
  caption,
  tall,
  src,
  credit,
}: {
  label: string;
  caption?: string;
  tall?: boolean;
  /** Path under /public. Omit to fall back to the dashed placeholder frame. */
  src?: string;
  credit?: string;
}) {
  return (
    <figure className={`primer-photo ${tall ? 'tall' : ''}`}>
      {src ? (
        <div className="primer-photo-frame primer-photo-frame-filled">
          <img src={src} alt={label} loading="lazy" />
        </div>
      ) : (
        <div className="primer-photo-frame">
          <span className="primer-photo-mark">▣</span>
          <span className="primer-photo-label">{label}</span>
          <span className="primer-photo-hint">image placeholder</span>
        </div>
      )}
      {(caption || credit) && (
        <figcaption>
          {caption}
          {credit && <span className="primer-photo-credit">{credit}</span>}
        </figcaption>
      )}
    </figure>
  );
}

function Formula({ expr, note }: { expr: ReactNode; note: string }) {
  return (
    <div className="primer-formula">
      <div className="primer-formula-expr">{expr}</div>
      <div className="primer-formula-note">{note}</div>
    </div>
  );
}

function TransitDiagram() {
  return (
    <div className="primer-diagram">
      <svg viewBox="0 0 260 155" role="img" aria-label="A planet crossing its star, and the dip it produces in the star's measured brightness">
        <defs>
          <radialGradient id="starGlow" cx="50%" cy="50%">
            <stop offset="0%" stopColor="#fff6e8" />
            <stop offset="60%" stopColor="#ffdca8" />
            <stop offset="100%" stopColor="#ffb765" stopOpacity="0.15" />
          </radialGradient>
        </defs>

        {/* star */}
        <circle cx="100" cy="45" r="46" fill="url(#starGlow)" opacity="0.28" />
        <circle cx="100" cy="45" r="34" fill="url(#starGlow)" />

        {/* planet, sweeping across the star's face */}
        <circle className="primer-diagram-planet" cx="0" cy="45" r="6" fill="#0a0716" />

        {/* brightness trace */}
        <text x="4" y="88" className="primer-diagram-axis">brightness</text>
        <path
          d="M 0,105 L 96,105 L 102,132 L 158,132 L 164,105 L 260,105"
          fill="none"
          stroke="#8be9c9"
          strokeWidth="1.6"
        />
        <line className="primer-diagram-scan" x1="0" y1="92" x2="0" y2="148" stroke="#ffffff" strokeWidth="0.8" strokeDasharray="2 3" opacity="0.55" />
        <text x="196" y="150" className="primer-diagram-axis">time →</text>
      </svg>
    </div>
  );
}

export default function Explainer({
  targetName = null,
  onContinue,
  onBack,
  embedded = false,
}: {
  targetName?: string | null;
  onContinue?: () => void;
  onBack?: () => void;
  /** True when shown as the "How it works" tab inside the app, rather than as
   * its own standalone page between the landing scene and the lab. */
  embedded?: boolean;
}) {
  return (
    <div className={`primer ${embedded ? 'primer-embedded' : ''}`}>
      {!embedded && (
        <header className="primer-top">
          <button className="primer-back" onClick={onBack}>
            ← back to orbit
          </button>
          <button className="primer-skip" onClick={onContinue}>
            skip to the lab →
          </button>
        </header>
      )}

      <section className="primer-hero">
        <p className="primer-eyebrow">A SHORT PRIMER</p>
        <h1>
          How do you find a planet
          <br />
          you can never see?
        </h1>
        <p className="primer-lede">
          Every star in the night sky is a sun, and most of them have planets. But a planet is
          roughly a billion times fainter than the star it orbits — like trying to spot a firefly
          sitting on a lighthouse, from the next city over. So we almost never look for the planet
          itself. We look for its <em>shadow</em>.
        </p>
      </section>

      <section className="primer-block">
        <p className="primer-index">01</p>
        <div className="primer-body">
          <h2>The shadow of a world</h2>
          <p>
            If a planet&rsquo;s orbit happens to lie edge-on to us, then once every orbit it slides
            directly between us and its star. For a few hours the star gets very slightly dimmer,
            then returns to normal. That dip is called a <strong>transit</strong>.
          </p>
          <p>
            One dip proves nothing — a cloud of dust, an instrument glitch, or a passing asteroid
            could do the same. But a dip that returns <em>on a strict schedule</em>, always the same
            depth and the same duration, is the fingerprint of something in a stable orbit.
          </p>
          <TransitDiagram />
          <p className="primer-caption">
            The planet crosses the star&rsquo;s disc; the measured brightness drops, holds flat while
            the planet is fully inside the disc, then climbs back. Roughly three quarters of all
            known exoplanets were found exactly this way.
          </p>
        </div>
        <PhotoPlaceholder
          label="Kepler space telescope"
          caption="The instrument that stared at one patch of sky for four years."
          src="/images/kepler-spacecraft.jpg"
          credit="NASA / PIA11733"
        />
      </section>

      <section className="primer-block">
        <p className="primer-index">02</p>
        <div className="primer-body">
          <h2>How deep is the shadow?</h2>
          <p>
            Almost embarrassingly simple: the fraction of light blocked is just the ratio of the two
            discs&rsquo; areas. Since area goes as radius squared —
          </p>
          <Formula
            expr={
              <>
                δ = ( R<sub>p</sub> / R<sub>★</sub> )<sup>2</sup>
              </>
            }
            note="δ (delta) is the transit depth — the fraction of starlight the planet blocks. Rp is the planet's radius, R★ the star's."
          />
          <p>
            Measure the depth, and you have the size of the planet. Here is what our own solar
            system would look like to a distant observer watching the Sun:
          </p>
          <table className="primer-table">
            <thead>
              <tr>
                <th>Planet crossing the Sun</th>
                <th>Depth</th>
                <th>In ppm</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Jupiter</td>
                <td>1.0%</td>
                <td>~10,000 ppm</td>
              </tr>
              <tr>
                <td>Neptune</td>
                <td>0.13%</td>
                <td>~1,250 ppm</td>
              </tr>
              <tr>
                <td>Earth</td>
                <td>0.0084%</td>
                <td>~84 ppm</td>
              </tr>
            </tbody>
          </table>
          <p>
            That last row is the whole challenge. To find another Earth you must measure a
            star&rsquo;s brightness to better than one part in ten thousand — using light that left
            it centuries ago, after it has passed through a telescope that is slowly warming,
            cooling and drifting.
          </p>
        </div>
        <PhotoPlaceholder
          label="Sun-like star"
          caption="Depth only tells you size relative to the host star."
          src="/images/sun-active-region.jpg"
          credit="NASA/SDO / PIA22645"
        />
      </section>

      <section className="primer-block primer-block-wide">
        <p className="primer-index">◆</p>
        <div className="primer-body">
          <h2>Try it yourself</h2>
          <p>
            Everything above is running live below. Drag the sliders and watch the dip — and the
            numbers — respond through the real equations, not a canned animation.
          </p>
          <TransitSimulator />
        </div>
      </section>

      <section className="primer-block">
        <p className="primer-index">03</p>
        <div className="primer-body">
          <h2>How far out does it orbit?</h2>
          <p>
            The time between one dip and the next is the planet&rsquo;s <strong>orbital period</strong>,
            P. Kepler&rsquo;s third law — the same one that governs our own planets — turns that
            period into a distance:
          </p>
          <Formula
            expr={
              <>
                a<sup>3</sup> = ( G · M<sub>★</sub> · P<sup>2</sup> ) / 4π<sup>2</sup>
              </>
            }
            note="a is the orbital radius, M★ the mass of the star, G the gravitational constant. Know the star, time the dips, and the orbit falls out."
          />
          <p>
            A 365-day period around a Sun-like star puts the planet at one astronomical unit —
            exactly where Earth sits. Most of what we actually detect orbits far closer in, and not
            because close-in planets are more common: a planet with a 3-day year gives you a hundred
            transits in a single year of observing, while an Earth twin gives you one.
          </p>
        </div>
        <PhotoPlaceholder
          label="Orbit geometry diagram"
          caption="Kepler-90's system next to our own — the target this app's demo catalog uses."
          src="/images/kepler-90-system.jpg"
          credit="NASA/Ames / PIA22193"
        />
      </section>

      <section className="primer-block">
        <p className="primer-index">04</p>
        <div className="primer-body">
          <h2>How long does the dip last?</h2>
          <p>
            Duration is a geometry problem — it depends on how fast the planet moves and how
            centrally it crosses the disc:
          </p>
          <Formula
            expr={
              <>
                T ≈ ( P / π ) · ( R<sub>★</sub> / a ) · √( 1 − b<sup>2</sup> )
              </>
            }
            note="T is the transit duration and b the impact parameter: 0 for a dead-centre crossing, 1 for a grazing one that clips the star's edge."
          />
          <p>
            This is one of our best lie detectors. Depth, duration and period are not independent —
            they are locked together by orbital mechanics. A dip that is far too long for its claimed
            period is telling you it is not a planet at all.
          </p>
        </div>
      </section>

      <section className="primer-block">
        <p className="primer-index">05</p>
        <div className="primer-body">
          <h2>Finding the rhythm</h2>
          <p>
            Here is the catch: we don&rsquo;t know the period in advance. So we guess — thousands of
            times. For every trial period we <strong>fold</strong> the light curve, wrapping the
            whole multi-year observation around that period so every cycle stacks on top of the
            others:
          </p>
          <Formula
            expr={<>φ = ( ( t − t<sub>0</sub> + P/2 ) mod P ) / P − 0.5</>}
            note="φ (phase) re-labels every measurement by where it falls within one orbit, from -0.5 to +0.5. This is the exact formula this app uses."
          />
          <p>
            Then we fit a <strong>box</strong> to the folded curve — a flat baseline with a single
            rectangular notch cut out of it — and ask how well it fits. Wrong period, and the real
            dips land at scattered phases and smear into nothing. Right period, and they all pile up
            in the same place and the box snaps into position. This is{' '}
            <strong>Box Least Squares</strong>, and the peak of its periodogram is the detection.
          </p>
          <p>
            Folding is also what makes the invisible visible. A 100-ppm dip buried under 500 ppm of
            noise is hopeless in a single orbit — but noise averages down as the square root of the
            number of measurements, while a real signal does not:
          </p>
          <Formula
            expr={
              <>
                SNR ≈ ( δ / σ ) · √N
              </>
            }
            note="σ is the scatter in the brightness measurements and N the number of in-transit points collected across every transit. Stack fifty orbits and a signal seven times too faint to see becomes obvious."
          />
        </div>
        <PhotoPlaceholder
          label="Phase-folded light curve"
          caption="Kepler-90 b, folded at its real 7.008-day period — generated from this app's own demo data."
          tall
          src="/images/phase-folded-curve.png"
        />
      </section>

      <section className="primer-block">
        <p className="primer-index">06</p>
        <div className="primer-body">
          <h2>Not everything that blinks is a planet</h2>
          <p>
            Most things that produce a clean, repeating dip are <em>not</em> planets. The usual
            culprit is a pair of stars orbiting each other, eclipsing one another on schedule. They
            leave tells, and we check every one:
          </p>
          <ul className="primer-list">
            <li>
              <strong>Too deep.</strong> Past roughly 3–5%, the object doing the blocking is
              star-sized, not planet-sized.
            </li>
            <li>
              <strong>A secondary eclipse.</strong> A second, shallower dip half a period later means
              the companion is bright enough to be missed when it goes behind — so it glows. Planets
              largely don&rsquo;t.
            </li>
            <li>
              <strong>Odd/even depth mismatch.</strong> If alternating dips have different depths,
              you have locked onto half the true period and are watching a binary&rsquo;s two
              different eclipses.
            </li>
            <li>
              <strong>V-shaped instead of flat-bottomed.</strong> A flat bottom means the planet is
              fully inside the star&rsquo;s disc. A V means a grazing clip — often a binary.
            </li>
          </ul>
          <p>
            Every one of these becomes a number this pipeline measures, and those numbers are what
            the models are fed.
          </p>
        </div>
        <PhotoPlaceholder
          label="Eclipsing binary pair"
          caption="The most common impostor."
          src="/images/eclipsing-binary-concept.jpg"
          credit="NASA/JPL-Caltech / PIA14726"
        />
      </section>

      <section className="primer-block">
        <p className="primer-index">07</p>
        <div className="primer-body">
          <h2>Teaching a machine to judge</h2>
          <p>Three models vote on every candidate this app finds:</p>
          <ul className="primer-list">
            <li>
              <strong>Gradient-boosted trees</strong> weigh the measured numbers — period, duration,
              depth, signal-to-noise, transit count — trained on NASA&rsquo;s catalogue of confirmed
              planets and known false positives.
            </li>
            <li>
              <strong>A convolutional network</strong> ignores the numbers and looks at the{' '}
              <em>shape</em> of the folded curve, in two views at once: a global view of the whole
              orbit, and a local view zoomed onto the dip itself.
            </li>
            <li>
              <strong>A small referee model</strong> weighs those two opinions against each other and
              produces the final confidence you see on each candidate.
            </li>
          </ul>
          <p className="primer-disclaimer">
            That score is a <strong>ranking, not a confirmation</strong>. Real validation takes
            follow-up observations, independent instruments, and often years. What this tool does is
            decide what deserves a closer look.
          </p>
        </div>
      </section>

      <section className="primer-cta">
        <h2>Now go find one.</h2>
        {embedded ? (
          <p>
            Switch to <strong>Demo catalog</strong> or <strong>Live MAST lookup</strong> above to
            run the whole pipeline on a real light curve.
          </p>
        ) : (
          <>
            <p>
              {targetName
                ? `You picked ${targetName}. Let's look at its actual starlight.`
                : 'Pull a real light curve from the NASA archive and run the whole pipeline on it.'}
            </p>
            <button className="primer-cta-button" onClick={onContinue}>
              {targetName ? `Open ${targetName} →` : 'Enter the lab →'}
            </button>
          </>
        )}
      </section>

      {!embedded && (
        <footer className="primer-footer">
          <span>TRANSIT LAB / PRIMER</span>
        </footer>
      )}
    </div>
  );
}

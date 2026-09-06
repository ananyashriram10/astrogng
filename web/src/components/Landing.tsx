import { useMemo, useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Html, OrbitControls, Stars } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import * as THREE from 'three';
import type { TargetSummary } from '../api';

type PlanetStyle = {
  color: string;
  size: number;
  distance: number;
  speed: number;
  inclination: number;
};

const ORIGIN = new THREE.Vector3(0, 0, 0);
const TRANSIT_ANGLE = 0.22;
const TRANSIT_DIM = 0.4;

// Muted bi-pride palette (dusty pink / soft lavender-purple / periwinkle
// blue) for the landing scene specifically — the rest of the app keeps its
// own palette untouched.
const BI_PINK = '#d98fc0';
const BI_PURPLE = '#9d84d9';
const BI_BLUE = '#6f92dd';
const BI_ROSE = '#c76b96'; // the "odd one out" accent for the false-positive demo

const PLANET_STYLES: Record<string, PlanetStyle> = {
  'Kepler-90': { color: BI_PURPLE, size: 0.42, distance: 1.7, speed: 0.18, inclination: 0.12 },
  'TRAPPIST-1': { color: BI_PINK, size: 0.34, distance: 2.32, speed: 0.13, inclination: -0.2 },
  'Kepler-10': { color: BI_BLUE, size: 0.26, distance: 1.16, speed: 0.26, inclination: 0.24 },
  'False-positive example': { color: BI_ROSE, size: 0.3, distance: 2.94, speed: 0.09, inclination: -0.1 },
};
const FALLBACK_STYLES: PlanetStyle[] = [
  { color: BI_PURPLE, size: 0.32, distance: 1.43, speed: 0.2, inclination: 0.1 },
  { color: BI_PINK, size: 0.29, distance: 1.96, speed: 0.15, inclination: -0.15 },
  { color: BI_BLUE, size: 0.34, distance: 2.58, speed: 0.1, inclination: 0.2 },
];

function styleFor(name: string, index: number): PlanetStyle {
  return PLANET_STYLES[name] ?? FALLBACK_STYLES[index % FALLBACK_STYLES.length];
}

function Star({ dimFactor }: { dimFactor: React.MutableRefObject<number> }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.MeshStandardMaterial>(null);
  const haloRef = useRef<THREE.MeshBasicMaterial>(null);

  useFrame((_, delta) => {
    if (meshRef.current) meshRef.current.rotation.y += delta * 0.05;
    const ease = Math.min(1, delta * 5);
    if (materialRef.current) {
      const targetIntensity = 1.5 * dimFactor.current;
      materialRef.current.emissiveIntensity += (targetIntensity - materialRef.current.emissiveIntensity) * ease;
    }
    if (haloRef.current) {
      const targetOpacity = 0.07 * dimFactor.current;
      haloRef.current.opacity += (targetOpacity - haloRef.current.opacity) * ease;
    }
  });

  return (
    <group>
      <pointLight position={[0, 0, 0]} intensity={2.6} color="#f3e6f7" distance={28} decay={1.5} />
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.56, 48, 48]} />
        <meshStandardMaterial
          ref={materialRef}
          color="#fdeef8"
          emissive="#e6b8dd"
          emissiveIntensity={1.5}
          toneMapped={false}
        />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.72, 32, 32]} />
        <meshBasicMaterial ref={haloRef} color="#8f7fd6" transparent opacity={0.07} side={THREE.BackSide} />
      </mesh>
    </group>
  );
}

function Planet({
  name,
  candidateCount,
  style,
  initialAngle,
  onSelect,
  positionsRef,
}: {
  name: string;
  candidateCount: number;
  style: PlanetStyle;
  initialAngle: number;
  onSelect: (name: string) => void;
  positionsRef: React.MutableRefObject<Record<string, THREE.Vector3>>;
}) {
  const angleRef = useRef(initialAngle);
  const groupRef = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);
  const reduceMotion = useMemo(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    [],
  );

  useFrame((_, delta) => {
    if (!reduceMotion) angleRef.current += delta * style.speed;
    const angle = angleRef.current;
    if (groupRef.current) {
      groupRef.current.position.set(
        Math.cos(angle) * style.distance,
        0,
        Math.sin(angle) * style.distance,
      );
      groupRef.current.rotation.y += reduceMotion ? 0 : delta * 0.6;
      groupRef.current.getWorldPosition(positionsRef.current[name]);
    }
  });

  return (
    <group rotation={[style.inclination, 0, 0]}>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[style.distance - 0.006, style.distance + 0.006, 96]} />
        <meshBasicMaterial color="#d9c8ec" transparent opacity={0.12} side={THREE.DoubleSide} />
      </mesh>
      <group ref={groupRef}>
        <mesh
          scale={hovered ? 1.25 : 1}
          onPointerOver={(e) => {
            e.stopPropagation();
            setHovered(true);
            document.body.style.cursor = 'pointer';
          }}
          onPointerOut={() => {
            setHovered(false);
            document.body.style.cursor = 'auto';
          }}
          onClick={(e) => {
            e.stopPropagation();
            onSelect(name);
          }}
        >
          <sphereGeometry args={[style.size, 32, 32]} />
          <meshStandardMaterial
            color={style.color}
            roughness={0.55}
            metalness={0.15}
            emissive={style.color}
            emissiveIntensity={hovered ? 0.55 : 0.15}
          />
        </mesh>
        {hovered && (
          <Html center distanceFactor={9} style={{ pointerEvents: 'none' }}>
            <div className="planet-label">
              <strong>{name}</strong>
              <span>
                {candidateCount} signal{candidateCount === 1 ? '' : 's'} · click to explore
              </span>
            </div>
          </Html>
        )}
      </group>
    </group>
  );
}

function TransitDimmer({
  positionsRef,
  dimFactor,
}: {
  positionsRef: React.MutableRefObject<Record<string, THREE.Vector3>>;
  dimFactor: React.MutableRefObject<number>;
}) {
  useFrame(({ camera }) => {
    const camToStar = ORIGIN.clone().sub(camera.position);
    const starDist = camToStar.length();
    let occluding = false;
    for (const pos of Object.values(positionsRef.current)) {
      const camToPlanet = pos.clone().sub(camera.position);
      if (camToPlanet.length() >= starDist - 0.05) continue;
      if (camToStar.angleTo(camToPlanet) < TRANSIT_ANGLE) {
        occluding = true;
        break;
      }
    }
    dimFactor.current = occluding ? TRANSIT_DIM : 1;
  });
  return null;
}

function Scene({
  targets,
  onSelect,
}: {
  targets: TargetSummary[];
  onSelect: (name: string) => void;
}) {
  const dimFactor = useRef(1);
  const positionsRef = useRef<Record<string, THREE.Vector3>>({});
  const planetConfigs = useMemo(
    () =>
      targets.map((item, index) => ({
        name: item.target,
        candidateCount: item.candidate_count,
        style: styleFor(item.target, index),
        initialAngle: Math.random() * Math.PI * 2,
      })),
    [targets],
  );
  for (const cfg of planetConfigs) {
    if (!positionsRef.current[cfg.name]) positionsRef.current[cfg.name] = new THREE.Vector3();
  }

  return (
    <>
      <ambientLight intensity={0.16} />
      <Stars radius={40} depth={20} count={1200} factor={1.8} saturation={0} fade speed={0.4} />
      <Star dimFactor={dimFactor} />
      {planetConfigs.map((cfg) => (
        <Planet
          key={cfg.name}
          name={cfg.name}
          candidateCount={cfg.candidateCount}
          style={cfg.style}
          initialAngle={cfg.initialAngle}
          onSelect={onSelect}
          positionsRef={positionsRef}
        />
      ))}
      <TransitDimmer positionsRef={positionsRef} dimFactor={dimFactor} />
      <OrbitControls
        enableZoom={false}
        enablePan={false}
        autoRotate={false}
        minPolarAngle={Math.PI / 2.6}
        maxPolarAngle={Math.PI / 1.7}
        minAzimuthAngle={-0.5}
        maxAzimuthAngle={0.5}
      />
      <EffectComposer>
        <Bloom luminanceThreshold={0.55} luminanceSmoothing={0.85} intensity={0.28} mipmapBlur />
      </EffectComposer>
    </>
  );
}

export default function Landing({
  targets,
  targetsError,
  onSelectTarget,
  onEnterLive,
  onLearnMore,
}: {
  targets: TargetSummary[];
  targetsError: string | null;
  onSelectTarget: (name: string) => void;
  onEnterLive: () => void;
  onLearnMore: () => void;
}) {
  return (
    <section className="landing">
      <div className="landing-main">
        <div className="landing-copy">
          <p className="eyebrow">EXOPLANET SIGNAL INTELLIGENCE</p>
          <h1>
            Find the worlds
            <br />
            <em>hidden in starlight.</em>
          </h1>
          <p className="intro">
            Transit Lab turns subtle, repeating dips in stellar brightness into ranked, explainable
            planet candidates — the same signal that gave us Kepler-90, TRAPPIST-1, and thousands of
            other worlds.
          </p>
          <p className="landing-hint">
            {targets.length > 0
              ? 'Click a world in orbit to open its light curve, or run a live lookup below.'
              : targetsError
                ? 'Demo catalog unavailable right now — you can still try a live lookup.'
                : 'Loading the demo catalog…'}
          </p>
          <div className="landing-actions">
            <button className="landing-cta secondary" onClick={onEnterLive}>
              Live MAST lookup →
            </button>
            {targets.length > 0 && (
              <button className="landing-cta ghost" onClick={() => onSelectTarget(targets[0].target)}>
                Skip to demo catalog
              </button>
            )}
            <button className="landing-cta ghost" onClick={onLearnMore}>
              How it works
            </button>
          </div>
        </div>

        <div className="landing-canvas-wrap">
          <Canvas
            camera={{ position: [0, 1.3, 6.2], fov: 44 }}
            gl={{ alpha: true, antialias: true }}
            dpr={[1, 2]}
          >
            <Scene targets={targets} onSelect={onSelectTarget} />
          </Canvas>
        </div>
      </div>

      <footer className="landing-footer">
        <span>TRANSIT LAB / HACKATHON BUILD</span>
      </footer>
    </section>
  );
}

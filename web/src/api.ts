export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000';

export type LightCurveSeries = {
  time: number[];
  flux: number[];
};

export type Candidate = {
  candidate_id: string;
  period_days: number;
  epoch_days: number;
  duration_hours: number;
  depth_ppm: number;
  snr: number;
  bls_power: number;
  confidence: number;
  disposition: 'planet-like' | 'likely false positive';
  num_transits_observed: number;
  odd_even_depth_diff_ppm: number;
  secondary_eclipse_depth_ppm: number;
  transit_shape_symmetry: number;
  phase: number[];
  folded_flux: number[];
  gbt_proba: number | null;
  cnn_proba: number | null;
  global_view: number[];
  local_view: number[];
  planet_radius_earth: number | null;
  semi_major_axis_au: number | null;
  equilibrium_temp_k: number | null;
  size_class: string | null;
  alias_of: string | null;
  alias_reason: string | null;
};

export type Periodogram = {
  period: number[];
  power: number[];
};

export type StellarProfile = {
  radius_solar: number | null;
  mass_solar: number | null;
  teff_k: number | null;
};

export type TargetMetadata = {
  requested_name?: string;
  mast_target?: string;
  identifier_type?: string;
  kepid?: number | null;
  kepoi_name?: string | null;
  kepler_name?: string | null;
  stellar_radius_solar?: number | null;
  stellar_mass_solar?: number | null;
  stellar_teff_k?: number | null;
  catalog_disposition?: string | null;
  catalog_period_days?: number | null;
  catalog_duration_hours?: number | null;
  catalog_depth_ppm?: number | null;
};

export type AnalysisResult = {
  target: string;
  mission: string;
  source: string;
  status: string;
  is_multi_planet: boolean;
  candidates: Candidate[];
  raw_light_curve: LightCurveSeries;
  detrended_light_curve: LightCurveSeries;
  notes: string[];
  classifier: string;
  target_metadata: TargetMetadata;
  periodogram: Periodogram | null;
  star: StellarProfile | null;
};

export type TargetSummary = {
  target: string;
  mission: string;
  candidate_count: number;
  is_multi_planet: boolean;
};

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    });
  } catch {
    throw new ApiError(
      `Could not reach the Transit Lab API at ${API_BASE}. Is uvicorn running?`,
    );
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (Array.isArray(body.detail)) {
        // FastAPI/pydantic validation errors: a list of {loc, msg, type}.
        detail = body.detail
          .map((err: { loc?: unknown[]; msg?: string }) => {
            const field = Array.isArray(err.loc) ? err.loc.at(-1) : undefined;
            return field ? `${field}: ${err.msg}` : err.msg ?? 'Invalid request';
          })
          .join('; ');
      } else if (typeof body.detail === 'string') {
        detail = body.detail;
      }
    } catch {
      // ignore body parse failure
    }
    throw new ApiError(detail);
  }
  return response.json() as Promise<T>;
}

export function fetchTargets(): Promise<TargetSummary[]> {
  return request<TargetSummary[]>('/targets');
}

export function fetchCandidates(target: string): Promise<AnalysisResult> {
  return request<AnalysisResult>(`/candidates/${encodeURIComponent(target)}`);
}

export type AnalyzeArchiveOptions = {
  target: string;
  mission: 'Kepler' | 'TESS';
  maxFiles: number;
  usePeriodHint: boolean;
};

export function analyzeArchiveTarget(options: AnalyzeArchiveOptions): Promise<AnalysisResult> {
  return request<AnalysisResult>('/analyze', {
    method: 'POST',
    body: JSON.stringify({
      target: options.target,
      mission: options.mission,
      use_archive: true,
      max_files: options.maxFiles,
      use_catalog_period_hint: options.usePeriodHint,
    }),
  });
}

export type ProgressEvent = { stage: string; detail: string };

/** Runs an archive analysis over SSE so the caller sees each stage as it happens. */
export function analyzeArchiveTargetStreamed(
  options: AnalyzeArchiveOptions,
  onProgress: (event: ProgressEvent) => void,
): { promise: Promise<AnalysisResult>; cancel: () => void } {
  const params = new URLSearchParams({
    target: options.target,
    mission: options.mission,
    max_files: String(options.maxFiles),
    use_catalog_period_hint: String(options.usePeriodHint),
  });
  const source = new EventSource(`${API_BASE}/analyze/stream?${params}`);

  let settled = false;
  const promise = new Promise<AnalysisResult>((resolve, reject) => {
    source.onmessage = (message) => {
      const payload = JSON.parse(message.data);
      if (payload.type === 'progress') {
        onProgress({ stage: payload.stage, detail: payload.detail });
      } else if (payload.type === 'result') {
        settled = true;
        source.close();
        resolve(payload.result as AnalysisResult);
      } else if (payload.type === 'error') {
        settled = true;
        source.close();
        reject(new ApiError(payload.message));
      }
    };
    source.onerror = () => {
      // EventSource also fires this on a normal server-side close, so only
      // treat it as a failure if no result or error arrived first.
      if (settled) return;
      settled = true;
      source.close();
      reject(
        new ApiError(
          `Lost the connection to the Transit Lab API at ${API_BASE} during analysis.`,
        ),
      );
    };
  });

  return {
    promise,
    cancel: () => {
      settled = true;
      source.close();
    },
  };
}

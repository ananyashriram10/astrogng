export function SkeletonBlock({ height, width }: { height: number | string; width?: number | string }) {
  return <div className="skeleton-block" style={{ height, width: width ?? '100%' }} />;
}

export function AnalysisSkeleton() {
  return (
    <div className="skeleton-wrap" aria-label="Loading analysis" aria-busy="true">
      <div className="stat-strip">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i}>
            <SkeletonBlock height={9} width={70} />
            <div style={{ height: 10 }} />
            <SkeletonBlock height={24} width={90} />
          </div>
        ))}
      </div>
      <section className="workspace">
        <div className="panel curve-panel">
          <SkeletonBlock height={270} />
        </div>
        <aside className="panel pipeline-panel">
          <SkeletonBlock height={270} />
        </aside>
      </section>
    </div>
  );
}

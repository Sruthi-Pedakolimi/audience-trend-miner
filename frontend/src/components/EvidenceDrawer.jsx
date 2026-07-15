function RejectedCluster({ item }) {
  return (
    <div className="border border-gray-300 border-dashed rounded-lg bg-gray-100/80 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
          Excluded
        </span>
        <span className="text-xs text-gray-400">{item.cluster_id}</span>
      </div>

      <ul className="flex flex-wrap gap-2 mb-3">
        {item.article_titles.map((title) => (
          <li
            key={title}
            className="text-sm text-gray-600 bg-white/60 border border-gray-200 rounded px-2 py-0.5 line-through decoration-gray-400"
          >
            {title}
          </li>
        ))}
      </ul>

      <p className="text-sm text-gray-600 leading-relaxed">
        <span className="font-medium text-gray-700">Why rejected: </span>
        {item.reason}
      </p>
    </div>
  )
}

export default function EvidenceDrawer({ rejected, loading, error }) {
  const count = rejected?.length ?? 0

  return (
    <section>
      <div className="mb-4 rounded-lg border border-gray-300 bg-gray-100 px-4 py-3">
        <h2 className="text-base font-medium text-gray-700">Noise filtering evidence</h2>
        <p className="text-sm text-gray-600 mt-1">
          These candidate clusters were reviewed and deliberately excluded — obituary
          spikes, incoherent groupings, and other non-viable audiences filtered out
          before synthesis.
        </p>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading exclusions...</p>}
      {error && <p className="text-sm text-red-600">Error: {error}</p>}
      {!loading && !error && count === 0 && (
        <p className="text-sm text-gray-500">No rejected clusters in this run.</p>
      )}

      <div className="space-y-3">
        {rejected?.map((item) => (
          <RejectedCluster key={item.cluster_id} item={item} />
        ))}
      </div>
    </section>
  )
}

function MetricBar({ label, value, max = 100, caption, title }) {
  const percent = Math.min(Math.max(value, 0), max)
  const width = max > 0 ? (percent / max) * 100 : 0

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600" title={title}>
          {label}
        </span>
        <span className="font-medium text-gray-900">
          {label === 'Traffic share' ? `${(value * 100).toFixed(1)}%` : value.toFixed(1)}
        </span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-slate-700 rounded-full"
          style={{ width: `${width}%` }}
        />
      </div>
      {caption && (
        <p className="mt-1 text-xs text-gray-500">{caption}</p>
      )}
    </div>
  )
}

function RatingBadge({ label, value }) {
  const colors = {
    high: 'bg-emerald-100 text-emerald-800',
    medium: 'bg-amber-100 text-amber-800',
    low: 'bg-gray-100 text-gray-700',
  }

  return (
    <div className="flex items-center justify-between text-sm py-1">
      <span className="text-gray-600">{label}</span>
      <span
        className={`px-2 py-0.5 rounded text-xs font-medium uppercase ${colors[value] ?? colors.low}`}
      >
        {value}
      </span>
    </div>
  )
}

function ScoreRow({ label, score }) {
  return (
    <div className="flex items-center justify-between text-sm py-1">
      <span className="text-gray-600">{label}</span>
      <span className="font-medium text-gray-900">{score}/5</span>
    </div>
  )
}

const BUYING_POWER_LABELS = {
  purchase_value: 'Purchase value',
  purchase_immediacy: 'Purchase immediacy',
  brand_category_breadth: 'Brand category breadth',
  trend_durability: 'Trend durability',
  overall_buying_power: 'Overall',
}

const EDITORIAL_LABELS = {
  cluster_coherence: 'Coherence',
  commercial_relevance: 'Commercial relevance',
  evidence_grounding: 'Evidence grounding',
  audience_specificity: 'Specificity',
  buying_power_justification: 'Buying power justification',
}

export default function PortfolioCard({ item }) {
  const { entry, metrics, editorial_review: review } = item
  const { buying_power: bp } = entry

  return (
    <article className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
      <header className="mb-4">
        <h2 className="text-xl font-semibold text-gray-900">{entry.name}</h2>
        <p className="mt-2 text-gray-700 leading-relaxed">
          {entry.trending_description}
        </p>
      </header>

      <section className="grid gap-3 mb-6 sm:grid-cols-2">
        <MetricBar label="Traffic share" value={metrics.traffic_share} max={1} />
        <MetricBar
          label="Size index"
          value={metrics.size_index}
          title="Log-normalized reach score, scaled 0–100 relative to other approved audiences in this batch."
          caption="Relative to this portfolio — 0 means lowest reach in the current batch, not zero traffic."
        />
      </section>

      <section className="mb-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-2">Buying power</h3>
        <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-1">
          {Object.entries(BUYING_POWER_LABELS).map(([key, label]) => (
            <RatingBadge key={key} label={label} value={bp[key]} />
          ))}
        </div>
        <p className="mt-2 text-sm text-gray-600">{bp.rationale}</p>
      </section>

      <section className="mb-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-2">Brand categories</h3>
        <div className="flex flex-wrap gap-2">
          {entry.brand_categories.map((category) => (
            <span
              key={category}
              className="px-2.5 py-1 text-xs font-medium bg-slate-100 text-slate-700 rounded-full"
            >
              {category}
            </span>
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-gray-900 mb-2">Editorial scores</h3>
        <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-1">
          {Object.entries(EDITORIAL_LABELS).map(([key, label]) => (
            <ScoreRow key={key} label={label} score={review.scores[key]} />
          ))}
        </div>
      </section>
    </article>
  )
}

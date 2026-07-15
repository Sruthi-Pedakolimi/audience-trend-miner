import { useCallback, useEffect, useState } from 'react'

const ARTICLE_LIMIT_OPTIONS = [10, 15, 20, 25]

function defaultWeekEnding() {
  const date = new Date()
  date.setDate(date.getDate() - 1)
  return date.toISOString().slice(0, 10)
}

function formatElapsed(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (mins === 0) return `${secs}s`
  return `${mins}m ${secs.toString().padStart(2, '0')}s`
}

export default function GeneratePanel({ onSuccess }) {
  const [weekEnding, setWeekEnding] = useState(defaultWeekEnding)
  const [articleLimit, setArticleLimit] = useState(15)
  const [dataMode, setDataMode] = useState('cached')
  const [cachedArticleLimits, setCachedArticleLimits] = useState([])
  const [generating, setGenerating] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [error, setError] = useState(null)

  const refreshCachedArticleLimits = useCallback(async (week) => {
    try {
      const response = await fetch(`/cached-article-limits?week_ending=${week}`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const json = await response.json()
      const limits = json.article_limits ?? []
      setCachedArticleLimits(limits)
      setArticleLimit((current) => {
        if (limits.length > 0 && !limits.includes(current)) {
          return limits[0]
        }
        return current
      })
      return limits
    } catch {
      setCachedArticleLimits([])
      return []
    }
  }, [])

  useEffect(() => {
    if (!generating) return undefined

    const startedAt = Date.now()
    setElapsedSeconds(0)

    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000))
    }, 1000)

    return () => clearInterval(interval)
  }, [generating])

  useEffect(() => {
    refreshCachedArticleLimits(weekEnding)
  }, [weekEnding, refreshCachedArticleLimits])

  function handleDataModeChange(mode) {
    setDataMode(mode)
    if (mode === 'cached' && cachedArticleLimits.length > 0) {
      if (!cachedArticleLimits.includes(articleLimit)) {
        setArticleLimit(cachedArticleLimits[0])
      }
    }
  }

  function isArticleLimitAvailable(limit) {
    if (dataMode === 'live') return true
    return cachedArticleLimits.includes(limit)
  }

  async function handleGenerate() {
    setGenerating(true)
    setError(null)

    try {
      const response = await fetch('/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          week_ending: weekEnding,
          article_limit: articleLimit,
          data_mode: dataMode,
          force_refresh: false,
        }),
      })

      const body = await response.json().catch(() => null)

      if (!response.ok) {
        const detail =
          typeof body?.detail === 'string'
            ? body.detail
            : body?.detail?.[0]?.msg ?? `Request failed (HTTP ${response.status})`
        throw new Error(detail)
      }

      await refreshCachedArticleLimits(body.week_ending ?? weekEnding)
      onSuccess(body)
    } catch (err) {
      setError(err.message ?? 'Something went wrong')
    } finally {
      setGenerating(false)
    }
  }

  const canGenerate =
    !generating &&
    weekEnding &&
    (dataMode === 'live' || cachedArticleLimits.includes(articleLimit))

  return (
    <section className="mb-6 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-medium text-gray-900 mb-3">Run configuration</h2>

      <div className="grid gap-4 sm:grid-cols-3 mb-4">
        <label className="block">
          <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">
            Week ending
          </span>
          <input
            type="date"
            value={weekEnding}
            onChange={(event) => setWeekEnding(event.target.value)}
            disabled={generating}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 disabled:bg-gray-100 disabled:text-gray-500"
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">
            Article limit
          </span>
          <select
            value={isArticleLimitAvailable(articleLimit) ? articleLimit : ''}
            onChange={(event) => setArticleLimit(Number(event.target.value))}
            disabled={generating || (dataMode === 'cached' && cachedArticleLimits.length === 0)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 disabled:bg-gray-100 disabled:text-gray-500"
          >
            {dataMode === 'cached' && cachedArticleLimits.length === 0 && (
              <option value="">No cached articles</option>
            )}
            {ARTICLE_LIMIT_OPTIONS.map((limit) => {
              const available = isArticleLimitAvailable(limit)
              return (
                <option key={limit} value={limit} disabled={!available}>
                  {limit}
                  {!available && dataMode === 'cached' ? ' (not cached)' : ''}
                </option>
              )
            })}
          </select>
        </label>

        <fieldset className="block">
          <legend className="text-xs font-medium text-gray-600 uppercase tracking-wide">
            Data mode
          </legend>
          <div className="mt-1 flex rounded-md border border-gray-300 overflow-hidden">
            <button
              type="button"
              onClick={() => handleDataModeChange('cached')}
              disabled={generating}
              className={`flex-1 px-3 py-2 text-sm font-medium transition-colors ${
                dataMode === 'cached'
                  ? 'bg-slate-700 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              } disabled:opacity-60`}
            >
              Cached
            </button>
            <button
              type="button"
              onClick={() => handleDataModeChange('live')}
              disabled={generating}
              className={`flex-1 px-3 py-2 text-sm font-medium transition-colors border-l border-gray-300 ${
                dataMode === 'live'
                  ? 'bg-slate-700 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              } disabled:opacity-60`}
            >
              Live
            </button>
          </div>
        </fieldset>
      </div>

      <button
        type="button"
        onClick={handleGenerate}
        disabled={!canGenerate}
        className="w-full sm:w-auto rounded-md bg-slate-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:bg-slate-400 disabled:cursor-not-allowed"
      >
        {generating ? 'Generating…' : 'Generate portfolio'}
      </button>

      {generating && (
        <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-sm font-medium text-slate-800">
            Generating audience portfolio — this may take up to a minute.
          </p>
          <p className="text-sm text-slate-600 mt-1">
            Elapsed: {formatElapsed(elapsedSeconds)}
          </p>
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm font-medium text-red-800">Generation failed</p>
          <p className="text-sm text-red-700 mt-1">{error}</p>
        </div>
      )}
    </section>
  )
}

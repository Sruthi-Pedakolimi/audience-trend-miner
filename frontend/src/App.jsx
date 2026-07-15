import { useState } from 'react'
import EvidenceDrawer from './components/EvidenceDrawer'
import GeneratePanel from './components/GeneratePanel'
import PortfolioCard from './components/PortfolioCard'

function App() {
  const [activeTab, setActiveTab] = useState('portfolio')
  const [portfolio, setPortfolio] = useState(null)
  const [rejected, setRejected] = useState(null)

  const approvedCount = portfolio?.portfolio?.length ?? 0
  const excludedCount = rejected?.length ?? 0
  const hasResults = portfolio !== null

  const tabClass = (tab) =>
    activeTab === tab
      ? 'bg-white text-gray-900 shadow-sm'
      : 'text-gray-600 hover:text-gray-900'

  function handleGenerateSuccess(data) {
    setPortfolio({
      generated_at: data.generated_at,
      cache_status: data.cache_status,
      week_ending: data.week_ending,
      article_limit: data.article_limit,
      data_mode: data.data_mode,
      portfolio: data.portfolio,
    })
    setRejected(data.rejected)
    setActiveTab('portfolio')
  }

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-3xl mx-auto">
        <header className="mb-4">
          <h1 className="text-2xl font-semibold text-gray-900">Audience Trend Miner</h1>
          {portfolio?.generated_at && (
            <p className="text-sm text-gray-500 mt-1">
              Generated {new Date(portfolio.generated_at).toLocaleString()}
              {portfolio.cache_status === 'hit' && (
                <span className="ml-2 text-gray-400">(cached result)</span>
              )}
            </p>
          )}
        </header>

        <GeneratePanel onSuccess={handleGenerateSuccess} />

        {hasResults && (
          <nav
            className="flex gap-1 p-1 mb-6 bg-gray-200 rounded-lg"
            aria-label="Portfolio views"
          >
            <button
              type="button"
              onClick={() => setActiveTab('portfolio')}
              className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors ${tabClass('portfolio')}`}
            >
              Approved audiences ({approvedCount})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('excluded')}
              className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors ${tabClass('excluded')}`}
            >
              Excluded ({excludedCount})
            </button>
          </nav>
        )}

        {!hasResults && (
          <p className="text-sm text-gray-600">
            Configure a run above and click Generate to build an audience portfolio from
            trending Wikipedia articles.
          </p>
        )}

        {activeTab === 'portfolio' && hasResults && (
          <>
            <div className="space-y-6">
              {portfolio.portfolio.map((item) => (
                <PortfolioCard key={item.cluster_id} item={item} />
              ))}
            </div>
            {excludedCount > 0 && (
              <p className="mt-6 text-sm text-gray-600">
                {excludedCount} cluster{excludedCount === 1 ? '' : 's'} excluded during
                review.{' '}
                <button
                  type="button"
                  onClick={() => setActiveTab('excluded')}
                  className="font-medium text-gray-900 underline underline-offset-2 hover:text-gray-700"
                >
                  View filtering evidence
                </button>
              </p>
            )}
          </>
        )}

        {activeTab === 'excluded' && hasResults && (
          <EvidenceDrawer rejected={rejected} loading={false} error={null} />
        )}
      </div>
    </main>
  )
}

export default App

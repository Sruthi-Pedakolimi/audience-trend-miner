import { useEffect, useState } from 'react'
import EvidenceDrawer from './components/EvidenceDrawer'
import PortfolioCard from './components/PortfolioCard'

function App() {
  const [activeTab, setActiveTab] = useState('portfolio')
  const [portfolio, setPortfolio] = useState(null)
  const [rejected, setRejected] = useState(null)
  const [portfolioError, setPortfolioError] = useState(null)
  const [rejectedError, setRejectedError] = useState(null)
  const [portfolioLoading, setPortfolioLoading] = useState(true)
  const [rejectedLoading, setRejectedLoading] = useState(true)

  useEffect(() => {
    fetch('/portfolio')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        return response.json()
      })
      .then((json) => {
        setPortfolio(json)
        setPortfolioLoading(false)
      })
      .catch((err) => {
        setPortfolioError(err.message)
        setPortfolioLoading(false)
      })

    fetch('/rejected')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        return response.json()
      })
      .then((json) => {
        setRejected(json.rejected)
        setRejectedLoading(false)
      })
      .catch((err) => {
        setRejectedError(err.message)
        setRejectedLoading(false)
      })
  }, [])

  const approvedCount = portfolio?.portfolio?.length ?? 0
  const excludedCount = rejected?.length ?? 0

  const tabClass = (tab) =>
    activeTab === tab
      ? 'bg-white text-gray-900 shadow-sm'
      : 'text-gray-600 hover:text-gray-900'

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-3xl mx-auto">
        <header className="mb-4">
          <h1 className="text-2xl font-semibold text-gray-900">Audience Trend Miner</h1>
          {portfolio?.generated_at && (
            <p className="text-sm text-gray-500 mt-1">
              Generated {new Date(portfolio.generated_at).toLocaleString()}
            </p>
          )}
        </header>

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

        {activeTab === 'portfolio' && (
          <>
            {portfolioLoading && <p className="text-gray-600">Loading portfolio...</p>}
            {portfolioError && <p className="text-red-600">Error: {portfolioError}</p>}
            <div className="space-y-6">
              {portfolio?.portfolio?.map((item) => (
                <PortfolioCard key={item.cluster_id} item={item} />
              ))}
            </div>
            {!portfolioLoading && excludedCount > 0 && (
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

        {activeTab === 'excluded' && (
          <EvidenceDrawer
            rejected={rejected}
            loading={rejectedLoading}
            error={rejectedError}
          />
        )}
      </div>
    </main>
  )
}

export default App

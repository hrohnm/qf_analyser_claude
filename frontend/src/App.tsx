import { Routes, Route } from 'react-router-dom'
import { AppLayout } from './components/layout/AppShell'
import { TodayPage } from './pages/TodayPage'
import { LeaguePage } from './pages/LeaguePage'
import { MatchDetailsPage } from './pages/MatchDetailsPage'
import { PlayersPage } from './pages/PlayersPage'
import { TeamPage } from './pages/TeamPage'
import { SyncPage } from './pages/SyncPage'
import { BettingSlipsPage } from './pages/BettingSlipsPage'
import { AdminPage } from './pages/AdminPage'
import { EvaluationPage } from './pages/EvaluationPage'

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<TodayPage />} />
        <Route path="/liga/:id" element={<LeaguePage />} />
        <Route path="/spieler" element={<PlayersPage />} />
        <Route path="/spiel/:fixtureId" element={<MatchDetailsPage />} />
        <Route path="/team/:teamId" element={<TeamPage />} />
        <Route path="/wettscheine" element={<BettingSlipsPage />} />
        <Route path="/auswertung" element={<EvaluationPage />} />
        <Route path="/sync" element={<SyncPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </AppLayout>
  )
}

import { Routes, Route } from 'react-router-dom'
import { AppLayout } from './components/layout/AppShell'
import { TodayPage } from './pages/TodayPage'
import { LeaguePage } from './pages/LeaguePage'
import { MatchDetailsPage } from './pages/MatchDetailsPage'
import { PlayersPage } from './pages/PlayersPage'
import { TeamPage } from './pages/TeamPage'
import { SyncPage } from './pages/SyncPage'

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<TodayPage />} />
        <Route path="/liga/:id" element={<LeaguePage />} />
        <Route path="/spieler" element={<PlayersPage />} />
        <Route path="/spiel/:fixtureId" element={<MatchDetailsPage />} />
        <Route path="/team/:teamId" element={<TeamPage />} />
        <Route path="/sync" element={<SyncPage />} />
      </Routes>
    </AppLayout>
  )
}

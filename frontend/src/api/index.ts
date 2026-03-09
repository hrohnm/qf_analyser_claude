import apiClient from './client'
import type {
  League,
  LeagueFormRow,
  Fixture,
  FixtureDetails,
  LeagueEloRow,
  PlayerOverview,
  TeamElo,
  TeamForm,
  TeamSummary,
  Budget,
  SyncResult,
  StandingRow,
} from '../types'

export const leaguesApi = {
  list: () => apiClient.get<League[]>('/leagues/').then(r => r.data),
  config: () => apiClient.get<League[]>('/leagues/config').then(r => r.data),
  elo: (leagueId: number, seasonYear: number) =>
    apiClient.get<LeagueEloRow[]>(`/leagues/${leagueId}/elo`, {
      params: { season_year: seasonYear },
    }).then(r => r.data),
  formTable: (leagueId: number, seasonYear: number, windowSize = 5, scope: 'overall' | 'home' | 'away' = 'overall') =>
    apiClient.get<LeagueFormRow[]>(`/leagues/${leagueId}/form-table`, {
      params: { season_year: seasonYear, window_size: windowSize, scope },
    }).then(r => r.data),
}

export const fixturesApi = {
  today: (forDate?: string) =>
    apiClient.get<Fixture[]>('/fixtures/today', {
      params: forDate ? { for_date: forDate } : {},
    }).then(r => r.data),

  list: (params: {
    league_id?: number
    season_year?: number
    status?: string
    matchday?: number
    limit?: number
    offset?: number
  }) => apiClient.get<Fixture[]>('/fixtures/', { params }).then(r => r.data),

  details: (fixtureId: number) =>
    apiClient.get<FixtureDetails>(`/fixtures/${fixtureId}/details`).then(r => r.data),
}

export const standingsApi = {
  get: (leagueId: number, seasonYear: number, upToMatchday?: number) =>
    apiClient.get<StandingRow[]>(`/standings/${leagueId}`, {
      params: {
        season_year: seasonYear,
        ...(upToMatchday != null ? { up_to_matchday: upToMatchday } : {}),
      },
    }).then(r => r.data),

  matchdays: (leagueId: number, seasonYear: number) =>
    apiClient.get<number[]>(`/standings/${leagueId}/matchdays`, {
      params: { season_year: seasonYear },
    }).then(r => r.data),
}

export const teamsApi = {
  summary: (teamId: number, seasonYear: number, leagueId?: number) =>
    apiClient.get<TeamSummary>(`/teams/${teamId}/summary`, {
      params: {
        season_year: seasonYear,
        ...(leagueId != null ? { league_id: leagueId } : {}),
      },
    }).then(r => r.data),
  elo: (teamId: number, seasonYear: number, leagueId: number) =>
    apiClient.get<TeamElo>(`/teams/${teamId}/elo`, {
      params: {
        season_year: seasonYear,
        league_id: leagueId,
      },
    }).then(r => r.data),
  form: (teamId: number, seasonYear: number, leagueId: number, windowSize = 5) =>
    apiClient.get<TeamForm>(`/teams/${teamId}/form`, {
      params: {
        season_year: seasonYear,
        league_id: leagueId,
        window_size: windowSize,
      },
    }).then(r => r.data),
}

export const playersApi = {
  overview: (params: {
    season_year: number
    league_id?: number
    team_id?: number
    limit?: number
    offset?: number
  }) => apiClient.get<PlayerOverview[]>('/players/overview', { params }).then(r => r.data),
}

export const syncApi = {
  budget: () => apiClient.get<Budget>('/sync/budget').then(r => r.data),
  triggerFixtures: (season_year?: number) =>
    apiClient.post<SyncResult>('/sync/fixtures/run', null, {
      params: season_year ? { season_year } : {},
    }).then(r => r.data),
  recomputeForm: (seasonYear: number, windowSize = 5, leagueId?: number) =>
    apiClient.post('/sync/form/run', null, {
      params: {
        season_year: seasonYear,
        window_size: windowSize,
        ...(leagueId != null ? { league_id: leagueId } : {}),
      },
    }).then(r => r.data),
}

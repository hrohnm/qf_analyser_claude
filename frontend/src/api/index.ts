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

export interface FixtureEvaluation {
  outcome_correct: boolean
  predicted_outcome: 'H' | 'D' | 'A'
  actual_outcome: 'H' | 'D' | 'A'
  p_actual_outcome: number
  dc_prediction: string | null
  dc_correct: boolean | null
  over_25_correct: boolean
  over_15_correct: boolean | null
  btts_correct: boolean
  home_scores_correct: boolean | null
  away_scores_correct: boolean | null
  score_correct: boolean
  predicted_score: string | null
  actual_score: string
  brier_score: number
  goals_diff: number
}

export interface EnrichedFixture extends Fixture {
  has_ai_picks: boolean
  p_home_win: number | null
  p_draw: number | null
  p_away_win: number | null
  p_btts: number | null
  p_over_15: number | null
  p_goal_home: number | null
  p_goal_away: number | null
  evaluation: FixtureEvaluation | null
}

export interface EvaluationRow {
  // Fixture fields
  id: number
  league_id: number
  league_name: string | null
  league_country: string | null
  home_team_name: string | null
  away_team_name: string | null
  kickoff_utc: string | null
  home_score: number | null
  away_score: number | null
  status_short: string | null
  // Evaluation fields
  actual_outcome: 'H' | 'D' | 'A'
  predicted_outcome: 'H' | 'D' | 'A'
  outcome_correct: boolean
  p_home_win: number
  p_draw: number
  p_away_win: number
  p_actual_outcome: number
  log_loss: number
  brier_score: number
  predicted_total_goals: number
  actual_total_goals: number
  goals_diff: number
  dc_prediction: string | null
  dc_prob: number | null
  dc_correct: boolean | null
  p_over_25: number
  predicted_over_25: boolean
  actual_over_25: boolean
  over_25_correct: boolean
  p_over_15: number | null
  over_15_correct: boolean | null
  p_btts: number
  predicted_btts: boolean
  actual_btts: boolean
  btts_correct: boolean
  p_home_scores: number | null
  home_scores_correct: boolean | null
  p_away_scores: number | null
  away_scores_correct: boolean | null
  predicted_score: string | null
  predicted_score_prob: number | null
  actual_score: string
  score_correct: boolean
  computed_at: string | null
  home_team_id: number | null
  away_team_id: number | null
}

export interface TeamProfileRow {
  rank: number
  team_id: number
  team_name: string
  team_logo_url: string | null
  games_played: number
  // Attack
  goals_scored_pg: number
  xg_for_pg: number | null
  shots_total_pg: number | null
  shots_on_target_pg: number | null
  shots_on_target_ratio: number | null
  shot_conversion_rate: number | null
  shots_inside_box_pg: number | null
  // Defense
  goals_conceded_pg: number
  clean_sheet_rate: number
  xg_against_pg: number | null
  shots_against_pg: number | null
  shots_on_target_against_pg: number | null
  gk_saves_pg: number | null
  // Style
  possession_avg: number | null
  passes_pg: number | null
  pass_accuracy_avg: number | null
  corners_pg: number | null
  fouls_pg: number | null
  yellow_cards_pg: number | null
  red_cards_pg: number | null
  offsides_pg: number | null
  // xG performance
  xg_over_performance: number | null
  xg_defense_performance: number | null
  // Ratings 0-100
  attack_rating: number | null
  defense_rating: number | null
  intensity_rating: number | null
  computed_at: string | null
  model_version: string
}

export interface LiveRefreshSettings {
  enabled: boolean
  interval_seconds: number
  interval_minutes: number
  min_interval_seconds: number
}

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
  teamProfiles: (leagueId: number, seasonYear: number, sortBy = 'attack_rating') =>
    apiClient.get<TeamProfileRow[]>(`/leagues/${leagueId}/team-profiles`, {
      params: { season_year: seasonYear, sort_by: sortBy },
    }).then(r => r.data),
}

export const fixturesApi = {
  today: (forDate?: string) =>
    apiClient.get<Fixture[]>('/fixtures/today', {
      params: forDate ? { for_date: forDate } : {},
    }).then(r => r.data),

  todayEnriched: (forDate?: string) =>
    apiClient.get<EnrichedFixture[]>('/fixtures/today/enriched', {
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

  evaluations: (params: {
    from_date?: string
    to_date?: string
    season_year?: number
    league_id?: number
  }) => apiClient.get<EvaluationRow[]>('/fixtures/evaluations', { params }).then(r => r.data),

  aiPicks: (fixtureId: number, force = false) =>
    apiClient.post(`/fixtures/${fixtureId}/ai-picks`, null, {
      params: force ? { force: true } : {},
    }).then(r => r.data),

  gptAnalysis: (fixtureId: number, force = false) =>
    apiClient.post(`/fixtures/${fixtureId}/gpt-analysis`, null, {
      params: force ? { force: true } : {},
    }).then(r => r.data),
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

export interface SlipPick {
  fixture_id: number
  home: string
  away: string
  league: string
  kickoff: string
  market: string
  pick: string
  bet_id: number
  bet_value: string
  odd: number
  probability?: number
  edge?: number
  betbuilder: boolean
  reasoning: string
  result: 'win' | 'loss' | 'push' | null
}

export interface CustomSlip {
  slip_nr: number
  name: string
  combined_odd: number
  n_games: number
  reasoning: string
  picks: SlipPick[]
  source: string
}

export interface CustomSlipParams {
  slip_date?: string
  league_ids?: number[]
  fixture_ids?: number[]
  target_odd?: number
  min_picks?: number
  max_picks?: number
  pick_odd_lo?: number
  pick_odd_hi?: number
  name?: string
}

export interface PlacedBet {
  id: number
  slip_date: string
  source: string
  slip_nr: number
  slip_name: string | null
  combined_odd: number
  stake: number | null
  status: 'placed' | 'won' | 'lost' | 'void'
  placed_at: string
  settled_at: string | null
}

export interface BettingStats {
  total_placed: number
  settled: number
  pending: number
  won: number
  lost: number
  win_rate: number | null
  total_staked: number | null
  total_return: number | null
  net_profit: number | null
  avg_odd_won: number | null
  avg_odd_lost: number | null
}

export const bettingSlipsApi = {
  get: (slipDate?: string, source: 'ai' | 'pattern' = 'ai') =>
    apiClient.get('/betting-slips/', { params: { ...(slipDate ? { slip_date: slipDate } : {}), source } })
      .then(r => r.data).catch(() => null),

  generate: (slipDate?: string, force = false) =>
    apiClient.post('/betting-slips/generate', null, {
      params: { ...(slipDate ? { slip_date: slipDate } : {}), ...(force ? { force: true } : {}) },
    }).then(r => r.data),

  generatePattern: (slipDate?: string, force = false) =>
    apiClient.post('/betting-slips/generate-pattern', null, {
      params: { ...(slipDate ? { slip_date: slipDate } : {}), ...(force ? { force: true } : {}) },
    }).then(r => r.data),

  regenerateSlip: (slipDate: string, slipNr: number) =>
    apiClient.post('/betting-slips/regenerate-slip', null, {
      params: { slip_date: slipDate, slip_nr: slipNr },
    }).then(r => r.data),

  placeBet: (body: {
    slip_date: string
    source: string
    slip_nr: number
    slip_name?: string
    combined_odd: number
    stake?: number
  }) => apiClient.post<PlacedBet>('/betting-slips/placed', body).then(r => r.data),

  settleBet: (id: number, status: 'won' | 'lost' | 'void') =>
    apiClient.patch<PlacedBet>(`/betting-slips/placed/${id}`, { status }).then(r => r.data),

  unplaceBet: (id: number) =>
    apiClient.delete(`/betting-slips/placed/${id}`).then(r => r.data),

  getPlacedBets: (slipDate?: string, source?: string) =>
    apiClient.get<PlacedBet[]>('/betting-slips/placed', {
      params: { ...(slipDate ? { slip_date: slipDate } : {}), ...(source ? { source } : {}) },
    }).then(r => r.data),

  getStats: (params?: { from_date?: string; to_date?: string; source?: string }) =>
    apiClient.get<BettingStats>('/betting-slips/stats', { params }).then(r => r.data),

  placeAll: (slipDate: string, stake = 10, source?: string) =>
    apiClient.post('/betting-slips/place-all', null, {
      params: { slip_date: slipDate, stake, ...(source ? { source } : {}) },
    }).then(r => r.data),

  evaluate: (slipDate: string, source?: string) =>
    apiClient.post('/betting-slips/evaluate', null, {
      params: { slip_date: slipDate, ...(source ? { source } : {}) },
    }).then(r => r.data),

  getHistory: (days = 14, source?: string) =>
    apiClient.get<Array<{
      slip_date: string
      slips: Array<{
        source: string
        slip_nr: number
        name: string
        combined_odd: number
        n_games: number | null
        placed: {
          id: number
          status: 'placed' | 'won' | 'lost' | 'void'
          stake: number | null
          combined_odd: number
          settled_at: string | null
        } | null
      }>
    }>>('/betting-slips/history', { params: { days, ...(source ? { source } : {}) } })
      .then(r => r.data),

  placeStrategy: (slipDate: string, source: 'pattern' | 'ai', stakes: Record<string, number>) =>
    apiClient.post('/betting-slips/place-strategy', { slip_date: slipDate, source, stakes })
      .then(r => r.data),

  getStatsBySlip: (source?: string) =>
    apiClient.get<Array<{
      name: string
      won: number
      lost: number
      total: number
      win_rate: number
      avg_odd: number
      ev: number
      profit: number
    }>>('/betting-slips/stats-by-slip', { params: source ? { source } : {} })
      .then(r => r.data),

  generateCustom: (params: CustomSlipParams) =>
    apiClient.post<{ slip_date: string; slip: CustomSlip }>('/betting-slips/generate-custom', params)
      .then(r => r.data),
}

export interface LeagueAdmin {
  id: number
  name: string
  country: string
  logo_url: string | null
  tier: number
  is_active: boolean
  current_season: number | null
}

export interface SyncEstimate {
  league_id: number
  league_name: string
  fixtures_in_db: number
  finished_fixtures: number
  already_have_stats: number
  already_have_events: number
  calls_fixtures: number
  calls_stats_needed: number
  calls_events_needed: number
  estimated_total_calls: number
  is_estimate: boolean
}

export interface SyncStatus {
  status: 'idle' | 'running' | 'done' | 'error'
  phase?: 'fixtures' | 'details'
  league_name?: string
  fixtures_loaded?: number
  details_fetched?: number
  details_skipped?: number
  api_calls_used?: number
  errors?: number
  error?: string
  started_at?: string
  finished_at?: string
}

export const adminApi = {
  listLeagues: () =>
    apiClient.get<LeagueAdmin[]>('/admin/leagues').then(r => r.data),

  fetchLeaguesFromApi: () =>
    apiClient.post<{
      total_from_api: number
      imported: number
      updated: number
      auto_activated: number
    }>('/admin/leagues/fetch-from-api').then(r => r.data),

  toggleLeague: (leagueId: number, isActive: boolean) =>
    apiClient.patch<{ id: number; is_active: boolean }>(
      `/admin/leagues/${leagueId}`,
      { is_active: isActive },
    ).then(r => r.data),

  syncEstimate: (leagueId: number, seasonYear = 2025) =>
    apiClient.get<SyncEstimate>(
      `/admin/leagues/${leagueId}/sync-estimate`,
      { params: { season_year: seasonYear } },
    ).then(r => r.data),

  activateAndSync: (leagueId: number, seasonYear = 2025) =>
    apiClient.post(
      `/admin/leagues/${leagueId}/activate-and-sync`,
      null,
      { params: { season_year: seasonYear } },
    ).then(r => r.data),

  syncStatus: (leagueId: number) =>
    apiClient.get<SyncStatus>(`/admin/leagues/${leagueId}/sync-status`).then(r => r.data),
}

export const syncApi = {
  budget: () => apiClient.get<Budget>('/sync/budget').then(r => r.data),
  liveRefreshSettings: () =>
    apiClient.get<LiveRefreshSettings>('/sync/live-refresh/settings').then(r => r.data),
  updateLiveRefreshSettings: (payload: { enabled?: boolean; interval_seconds?: number }) =>
    apiClient.patch<LiveRefreshSettings>('/sync/live-refresh/settings', payload).then(r => r.data),
  triggerFixtures: (season_year?: number) =>
    apiClient.post<SyncResult>('/sync/fixtures/run', null, {
      params: season_year ? { season_year } : {},
    }).then(r => r.data),
  refreshLiveToday: (seasonYear = 2025) =>
    apiClient.post<{
      message: string
      season_year: number
      leagues: number
      fixtures: number
      results: Array<Record<string, unknown>>
    }>('/sync/fixtures/live-today/run', null, {
      params: { season_year: seasonYear },
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

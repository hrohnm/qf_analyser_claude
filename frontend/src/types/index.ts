export interface League {
  id: number
  name: string
  country: string
  tier: number
  current_season: number | null
  logo_url: string | null
  is_active: boolean
}

export interface Fixture {
  id: number
  league_id: number
  league_name: string | null
  league_country: string | null
  league_tier: number | null
  season_year: number
  home_team_id: number
  away_team_id: number
  home_team_name: string | null
  away_team_name: string | null
  kickoff_utc: string | null
  round: string | null
  matchday: number | null
  status_short: string | null
  home_score: number | null
  away_score: number | null
  home_ht_score: number | null
  away_ht_score: number | null
  venue_name: string | null
}

export interface FixtureStatistic {
  team_id: number
  team_name: string | null
  team_logo_url: string | null
  shots_on_goal: number | null
  shots_off_goal: number | null
  shots_total: number | null
  shots_blocked: number | null
  shots_inside_box: number | null
  shots_outside_box: number | null
  fouls: number | null
  corner_kicks: number | null
  offsides: number | null
  ball_possession: number | null
  yellow_cards: number | null
  red_cards: number | null
  goalkeeper_saves: number | null
  passes_total: number | null
  passes_accurate: number | null
  pass_accuracy: number | null
  expected_goals: number | null
}

export interface FixtureEvent {
  id: number
  team_id: number
  team_name: string | null
  elapsed: number | null
  elapsed_extra: number | null
  event_type: string | null
  detail: string | null
  comments: string | null
  player_id: number | null
  player_name: string | null
  assist_id: number | null
  assist_name: string | null
}

export interface FixtureDetails {
  fixture: Fixture
  prediction: {
    winner_team_id: number | null
    winner_name: string | null
    winner_comment: string | null
    win_or_draw: boolean | null
    under_over: string | null
    advice: string | null
    percent_home: number | null
    percent_draw: number | null
    percent_away: number | null
    fetched_at: string | null
  } | null
  goal_probability_home: {
    team_id: number
    is_home: boolean
    lambda_weighted: number
    p_ge_1_goal: number
    p_ge_2_goals: number
    p_ge_3_goals: number
    confidence: number
    sample_size: number
    computed_at: string | null
    model_version: string
  } | null
  goal_probability_away: {
    team_id: number
    is_home: boolean
    lambda_weighted: number
    p_ge_1_goal: number
    p_ge_2_goals: number
    p_ge_3_goals: number
    confidence: number
    sample_size: number
    computed_at: string | null
    model_version: string
  } | null
  concede_probability_home: {
    team_id: number
    is_home: boolean
    lambda_weighted: number
    p_ge_1_goal: number
    p_ge_2_goals: number
    p_ge_3_goals: number
    confidence: number
    sample_size: number
    computed_at: string | null
    model_version: string
  } | null
  concede_probability_away: {
    team_id: number
    is_home: boolean
    lambda_weighted: number
    p_ge_1_goal: number
    p_ge_2_goals: number
    p_ge_3_goals: number
    confidence: number
    sample_size: number
    computed_at: string | null
    model_version: string
  } | null
  match_goal_lines: {
    home: {
      plus_0_5: number
      plus_1_5: number
      lambda_base: number
      lambda_final: number
      factors: {
        home_advantage: number
        elo: number
        form: number
      }
    }
    away: {
      plus_0_5: number
      plus_1_5: number
      lambda_base: number
      lambda_final: number
      factors: {
        home_advantage: number
        elo: number
        form: number
      }
    }
  } | null
  injuries: Array<{
    team_id: number | null
    team_name: string | null
    player_id: number | null
    player_name: string | null
    injury_type: string | null
    injury_reason: string | null
    fetched_at: string | null
  }>
  injury_impacts: Array<{
    team_id: number | null
    player_id: number | null
    player_name: string | null
    impact_score: number
    impact_bucket: string
    importance_score: number
    contribution_score: number
    replaceability_score: number
    availability_factor: number
    confidence: number
    model_version: string
    computed_at: string | null
  }>
  team_injury_impact_home: number
  team_injury_impact_away: number
  statistics: FixtureStatistic[]
  events: FixtureEvent[]
  pattern_evaluation: PatternEvaluation | null
  h2h: {
    matches_total: number
    home_wins: number
    draws: number
    away_wins: number
    home_win_pct: number
    draw_pct: number
    away_win_pct: number
    avg_goals_home: number
    avg_goals_away: number
    avg_total_goals: number
    btts_rate: number
    over_25_rate: number
    h2h_score: number
  } | null
  goal_timing_home: {
    games_played: number
    goals_scored: number
    timing_attack: Record<string, { goals: number; rate: number; index: number }> | null
    ht_attack_ratio: number | null
    profil_typ: string | null
    p_goal_first_30: number | null
    p_goal_last_15: number | null
  } | null
  goal_timing_away: {
    games_played: number
    goals_scored: number
    timing_attack: Record<string, { goals: number; rate: number; index: number }> | null
    ht_attack_ratio: number | null
    profil_typ: string | null
    p_goal_first_30: number | null
    p_goal_last_15: number | null
  } | null
  home_advantage_home: {
    home_ppg: number
    away_ppg: number
    advantage_factor: number
    normalized_factor: number
    tier: string
    games_home: number
    games_away: number
  } | null
  home_advantage_away: {
    home_ppg: number
    away_ppg: number
    advantage_factor: number
    normalized_factor: number
    tier: string
    games_home: number
    games_away: number
  } | null
  scoreline_distribution: {
    lambda_home: number
    lambda_away: number
    p_home_win: number
    p_draw: number
    p_away_win: number
    p_btts: number
    p_over_15: number
    p_over_25: number
    p_over_35: number
    p_home_clean_sheet: number
    p_away_clean_sheet: number
    most_likely_score: string | null
    most_likely_score_prob: number
  } | null
  match_result_probability: {
    p_home_win: number
    p_draw: number
    p_away_win: number
    p_btts: number
    p_over_25: number
    p_over_15: number
    p_over_35: number
    confidence: number
    elo_home_prob: number | null
    elo_away_prob: number | null
  } | null
  value_bets: Array<{
    market_name: string
    bet_value: string
    model_prob: number
    bookmaker_odd: number
    implied_prob: number
    edge: number
    expected_value: number
    kelly_fraction: number
    fair_odd: number
    tier: string
  }> | null
}

export interface PatternEvaluation {
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
}

export interface TeamLastMatch {
  fixture_id: number
  kickoff_utc: string | null
  league_id: number
  opponent_team_id: number
  opponent_team_name: string
  is_home: boolean
  goals_for: number | null
  goals_against: number | null
  result: 'W' | 'D' | 'L' | null
}

export interface TeamSummary {
  team_id: number
  team_name: string
  team_logo_url: string | null
  season_year: number
  league_id: number | null
  played: number
  won: number
  drawn: number
  lost: number
  points: number
  goals_for: number
  goals_against: number
  goal_diff: number
  goals_for_home: number
  goals_against_home: number
  goals_for_away: number
  goals_against_away: number
  form: string
  home_played: number
  home_points: number
  away_played: number
  away_points: number
  avg_goals_for: number
  avg_goals_against: number
  xg_total: number | null
  xg_total_home: number | null
  xg_total_away: number | null
  avg_ball_possession: number | null
  avg_ball_possession_home: number | null
  avg_ball_possession_away: number | null
  shots_total: number
  shots_total_home: number
  shots_total_away: number
  shots_on_goal: number
  shots_on_goal_home: number
  shots_on_goal_away: number
  corners: number
  corners_home: number
  corners_away: number
  fouls: number
  fouls_home: number
  fouls_away: number
  yellow_cards: number
  yellow_cards_home: number
  yellow_cards_away: number
  red_cards: number
  red_cards_home: number
  red_cards_away: number
  passes_total: number
  passes_total_home: number
  passes_total_away: number
  passes_accurate: number
  passes_accurate_home: number
  passes_accurate_away: number
  pass_accuracy_pct: number | null
  events_goals: number
  events_goals_home: number
  events_goals_away: number
  events_yellow_cards: number
  events_yellow_cards_home: number
  events_yellow_cards_away: number
  events_red_cards: number
  events_red_cards_home: number
  events_red_cards_away: number
  events_substitutions: number
  events_substitutions_home: number
  events_substitutions_away: number
  last_matches: TeamLastMatch[]
}

export interface TeamElo {
  team_id: number
  team_name: string
  team_logo_url: string | null
  league_id: number
  season_year: number
  elo_overall: number
  elo_home: number
  elo_away: number
  games_played: number
  games_home: number
  games_away: number
  elo_delta_last_5: number
  strength_tier: string
  computed_at: string | null
  model_version: string
}

export interface LeagueEloRow {
  rank: number
  team_id: number
  team_name: string
  team_logo_url: string | null
  elo_overall: number
  elo_home: number
  elo_away: number
  games_played: number
  elo_delta_last_5: number
  strength_tier: string
  computed_at: string | null
  model_version: string
}

export interface TeamFormScope {
  scope: 'overall' | 'home' | 'away'
  form_score: number
  result_score: number
  performance_score: number
  trend_score: number
  opponent_strength_score: number
  elo_adjusted_result_score: number
  form_trend: 'up' | 'flat' | 'down'
  form_bucket: 'schwach' | 'mittel' | 'stark'
  games_considered: number
  computed_at: string | null
  model_version: string
}

export interface TeamForm {
  team_id: number
  team_name: string
  team_logo_url: string | null
  league_id: number
  season_year: number
  window_size: number
  scopes: TeamFormScope[]
}

export interface LeagueFormRow {
  rank: number
  team_id: number
  team_name: string
  team_logo_url: string | null
  scope: 'overall' | 'home' | 'away'
  form_score: number
  result_score: number
  performance_score: number
  trend_score: number
  opponent_strength_score: number
  elo_adjusted_result_score: number
  form_trend: 'up' | 'flat' | 'down'
  form_bucket: 'schwach' | 'mittel' | 'stark'
  games_considered: number
  computed_at: string | null
  model_version: string
}

export interface PlayerOverview {
  player_id: number | null
  player_name: string
  team_id: number | null
  team_name: string | null
  team_logo_url: string | null
  matches: number
  goals: number
  assists: number
  yellow_cards: number
  red_cards: number
  substitutions: number
  events_total: number
  first_event_utc: string | null
  last_event_utc: string | null
}

export interface Budget {
  used_today: number
  remaining: number
  limit: number
  date: string
}

export interface SyncResult {
  message: string
  season_year: number
  results: Array<{
    league_id: number
    league_name: string
    count?: number
    error?: string
  }> | null
}

export interface StandingRow {
  rank: number
  team_id: number
  team_name: string
  logo_url: string
  played: number
  won: number
  drawn: number
  lost: number
  goals_for: number
  goals_against: number
  goal_diff: number
  points: number
  form: string
}

export type MatchStatus = 'NS' | '1H' | 'HT' | '2H' | 'FT' | 'AET' | 'PEN' | 'CANC' | 'PST' | 'TBD'

export const STATUS_LABELS: Record<string, string> = {
  NS: 'Geplant',
  '1H': '1. Halbzeit',
  HT: 'Halbzeit',
  '2H': '2. Halbzeit',
  FT: 'Beendet',
  AET: 'n.V.',
  PEN: 'Elfm.',
  CANC: 'Abgesagt',
  PST: 'Verschoben',
  TBD: 'Offen',
}

export const COUNTRY_FLAGS: Record<string, string> = {
  Germany: '🇩🇪',
  France: '🇫🇷',
  Italy: '🇮🇹',
  Spain: '🇪🇸',
  England: '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
  Turkey: '🇹🇷',
}

export const COUNTRY_CODES: Record<string, string> = {
  Germany: 'de',
  France: 'fr',
  Italy: 'it',
  Spain: 'es',
  England: 'gb-eng',
  Turkey: 'tr',
}

export const teamLogoUrl = (teamId: number) =>
  `https://media.api-sports.io/football/teams/${teamId}.png`

export const playerImageUrl = (playerId: number) =>
  `https://media.api-sports.io/football/players/${playerId}.png`

export const leagueLogoUrl = (leagueId: number) =>
  `https://media.api-sports.io/football/leagues/${leagueId}.png`

export const countryFlagUrl = (country: string) => {
  const code = COUNTRY_CODES[country]
  return code ? `https://media.api-sports.io/flags/${code}.svg` : ''
}

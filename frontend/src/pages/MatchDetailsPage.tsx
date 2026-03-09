import {
  Alert,
  Avatar,
  Badge,
  Card,
  Center,
  Divider,
  Grid,
  GridCol,
  Group,
  Loader,
  Progress,
  RingProgress,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from '@mantine/core'
import { IconArrowLeft, IconInfoCircle } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { useNavigate, useParams } from 'react-router-dom'
import { fixturesApi, leaguesApi, teamsApi } from '../api'
import type { FixtureStatistic, TeamLastMatch } from '../types'
import { leagueLogoUrl, playerImageUrl, STATUS_LABELS, teamLogoUrl } from '../types'

function fmtMinute(elapsed: number | null, extra: number | null) {
  if (elapsed == null) return '–'
  return extra != null ? `${elapsed}+${extra}'` : `${elapsed}'`
}

function statValue(stat: FixtureStatistic | undefined, key: keyof FixtureStatistic): number | null {
  const v = stat?.[key]
  return typeof v === 'number' ? v : null
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  Goal: 'Tor',
  Card: 'Karte',
  subst: 'Wechsel',
  Var: 'VAR',
}

const EVENT_DETAIL_LABELS: Record<string, string> = {
  'Normal Goal': 'Normales Tor',
  'Own Goal': 'Eigentor',
  Penalty: 'Elfmeter',
  'Missed Penalty': 'Elfmeter verschossen',
  'Penalty cancelled': 'Elfmeter aberkannt',
  'Goal Disallowed': 'Tor aberkannt',
  'Yellow Card': 'Gelbe Karte',
  'Red Card': 'Rote Karte',
  'Second Yellow card': 'Gelb-Rote Karte',
}

function translateEventType(value: string | null) {
  if (!value) return null
  return EVENT_TYPE_LABELS[value] ?? value
}

function translateEventDetail(value: string | null) {
  if (!value) return null
  if (value.startsWith('Substitution')) return 'Wechsel'
  return EVENT_DETAIL_LABELS[value] ?? value
}

function StatRow({
  label,
  home,
  away,
}: {
  label: string
  home: number | null
  away: number | null
}) {
  const a = home ?? 0
  const b = away ?? 0
  const total = a + b
  const pct = total > 0 ? Math.round((a / total) * 100) : 50
  const formatVal = (v: number | null) => {
    if (v == null) return '–'
    if (Number.isInteger(v)) return String(v)
    return v.toFixed(1).replace('.', ',')
  }

  return (
    <Stack gap={4}>
      <Group justify="space-between">
        <Text size="sm" fw={600}>{formatVal(home)}</Text>
        <Text size="xs" c="dimmed">{label}</Text>
        <Text size="sm" fw={600}>{formatVal(away)}</Text>
      </Group>
      <Progress.Root size={10}>
        <Progress.Section value={pct} color="blue" />
        <Progress.Section value={100 - pct} color="gray" />
      </Progress.Root>
    </Stack>
  )
}

function fmtValue(v: number | null) {
  if (v == null) return '–'
  if (Number.isInteger(v)) return String(v)
  return v.toFixed(1).replace('.', ',')
}

function fmtElo(v: number | null | undefined) {
  if (v == null) return '–'
  return v.toFixed(1).replace('.', ',')
}

function fmtPct(v: number | null | undefined) {
  if (v == null) return '–'
  return `${(v * 100).toFixed(1).replace('.', ',')}%`
}

function impactBadgeColor(bucket: string | null) {
  if (bucket === 'kritisch') return 'red'
  if (bucket === 'hoch') return 'orange'
  if (bucket === 'mittel') return 'yellow'
  return 'gray'
}

function formResultColor(c: string) {
  if (c === 'W') return 'green'
  if (c === 'D') return 'yellow'
  if (c === 'L') return 'red'
  return 'gray'
}

function formResultLabel(c: string) {
  if (c === 'W') return 'S'
  if (c === 'D') return 'U'
  if (c === 'L') return 'N'
  return c
}

function resultQualityLabel(
  result: string | null | undefined,
  ownElo: number | undefined,
  oppElo: number | undefined,
) {
  if (!result || ownElo == null || oppElo == null) return 'Einordnung n/v'
  const diff = ownElo - oppElo
  if (result === 'W') {
    if (diff <= -60) return 'Starker Sieg (gegen klar stärkeres Team)'
    if (diff >= 60) return 'Pflichtsieg (gegen schwächeres Team)'
    return 'Solider Sieg'
  }
  if (result === 'D') {
    if (diff <= -60) return 'Starkes Remis'
    if (diff >= 60) return 'Enttäuschendes Remis'
    return 'Ordentliches Remis'
  }
  if (diff <= -60) return 'Akzeptable Niederlage'
  if (diff >= 60) return 'Schwache Niederlage'
  return 'Normale Niederlage'
}

function LastFiveForm({
  lastMatches,
  ownElo,
  eloByTeam,
  rankByTeam,
}: {
  lastMatches: TeamLastMatch[] | undefined
  ownElo: number | undefined
  eloByTeam: Record<number, number>
  rankByTeam: Record<number, number>
}) {
  const matches = (lastMatches ?? []).slice(0, 5)
  if (!matches.length) {
    return <Text size="xs" c="dimmed">Letzte 5: n/v</Text>
  }
  return (
    <Group gap={4} wrap="nowrap">
      {matches.map((m, i) => {
        const c = m.result ?? '-'
        const oppElo = eloByTeam[m.opponent_team_id]
        const oppRank = rankByTeam[m.opponent_team_id]
        const quality = resultQualityLabel(m.result, ownElo, oppElo)
        const venue = m.is_home ? 'Heim' : 'Auswärts'
        const score = m.goals_for != null && m.goals_against != null ? `${m.goals_for}:${m.goals_against}` : '–'
        return (
          <Tooltip
            key={`${m.fixture_id}-${i}`}
            label={`${venue} vs ${m.opponent_team_name} · ${score} · Elo ${oppElo?.toFixed(1).replace('.', ',') ?? 'n/v'}${oppRank ? ` (#${oppRank})` : ''} · ${quality}`}
            multiline
            w={320}
          >
            <Badge size="xs" color={formResultColor(c)} variant="filled">
              {formResultLabel(c)}
            </Badge>
          </Tooltip>
        )
      })}
    </Group>
  )
}

function formRingColor(score: number | null) {
  if (score == null) return 'gray'
  if (score >= 70) return 'green'
  if (score >= 40) return 'yellow'
  return 'red'
}

function FormLogo({
  teamId,
  teamName,
  formScore,
  trend,
}: {
  teamId: number
  teamName: string
  formScore: number | null
  trend: string | null
}) {
  const color = formRingColor(formScore)
  const value = formScore ?? 0
  return (
    <Tooltip
      label={`Form: ${formScore != null ? formScore.toFixed(1).replace('.', ',') : 'n/v'}${trend ? ` · Trend: ${trend}` : ''}`}
      position="bottom"
    >
      <RingProgress
        size={88}
        thickness={5}
        roundCaps
        sections={[{ value, color }]}
        label={
          <img
            src={teamLogoUrl(teamId)}
            width={46}
            height={46}
            alt={teamName}
            style={{ display: 'block', margin: '0 auto', objectFit: 'contain' }}
          />
        }
      />
    </Tooltip>
  )
}

export function MatchDetailsPage() {
  const { fixtureId } = useParams<{ fixtureId: string }>()
  const navigate = useNavigate()
  const id = Number(fixtureId)

  const { data, isLoading, error } = useQuery({
    queryKey: ['fixture-details', id],
    queryFn: () => fixturesApi.details(id),
    enabled: Number.isFinite(id) && id > 0,
  })

  const fixtureForQuery = data?.fixture

  const { data: homeTeamSummary } = useQuery({
    queryKey: ['team-summary', fixtureForQuery?.home_team_id, fixtureForQuery?.season_year, fixtureForQuery?.league_id],
    queryFn: () => teamsApi.summary(fixtureForQuery!.home_team_id, fixtureForQuery!.season_year, fixtureForQuery!.league_id),
    enabled: !!fixtureForQuery,
  })

  const { data: awayTeamSummary } = useQuery({
    queryKey: ['team-summary', fixtureForQuery?.away_team_id, fixtureForQuery?.season_year, fixtureForQuery?.league_id],
    queryFn: () => teamsApi.summary(fixtureForQuery!.away_team_id, fixtureForQuery!.season_year, fixtureForQuery!.league_id),
    enabled: !!fixtureForQuery,
  })

  const { data: homeTeamElo } = useQuery({
    queryKey: ['team-elo', fixtureForQuery?.home_team_id, fixtureForQuery?.season_year, fixtureForQuery?.league_id],
    queryFn: () => teamsApi.elo(fixtureForQuery!.home_team_id, fixtureForQuery!.season_year, fixtureForQuery!.league_id),
    enabled: !!fixtureForQuery,
  })

  const { data: awayTeamElo } = useQuery({
    queryKey: ['team-elo', fixtureForQuery?.away_team_id, fixtureForQuery?.season_year, fixtureForQuery?.league_id],
    queryFn: () => teamsApi.elo(fixtureForQuery!.away_team_id, fixtureForQuery!.season_year, fixtureForQuery!.league_id),
    enabled: !!fixtureForQuery,
  })

  const { data: leagueEloRows = [] } = useQuery({
    queryKey: ['league-elo', fixtureForQuery?.league_id, fixtureForQuery?.season_year],
    queryFn: () => leaguesApi.elo(fixtureForQuery!.league_id, fixtureForQuery!.season_year),
    enabled: !!fixtureForQuery,
  })

  const { data: homeTeamForm } = useQuery({
    queryKey: ['team-form', fixtureForQuery?.home_team_id, fixtureForQuery?.season_year, fixtureForQuery?.league_id, 5],
    queryFn: () => teamsApi.form(fixtureForQuery!.home_team_id, fixtureForQuery!.season_year, fixtureForQuery!.league_id, 5),
    enabled: !!fixtureForQuery,
  })

  const { data: awayTeamForm } = useQuery({
    queryKey: ['team-form', fixtureForQuery?.away_team_id, fixtureForQuery?.season_year, fixtureForQuery?.league_id, 5],
    queryFn: () => teamsApi.form(fixtureForQuery!.away_team_id, fixtureForQuery!.season_year, fixtureForQuery!.league_id, 5),
    enabled: !!fixtureForQuery,
  })

  if (isLoading) return <Center py="xl"><Loader /></Center>
  if (error || !data) return <Alert color="red" title="Fehler">Match-Details konnten nicht geladen werden.</Alert>

  const {
    fixture,
    prediction,
    goal_probability_home,
    goal_probability_away,
    concede_probability_home,
    concede_probability_away,
    match_goal_lines,
    injuries,
    injury_impacts,
    team_injury_impact_home,
    team_injury_impact_away,
    statistics,
    events,
  } = data
  const home = fixture.home_team_name ?? `Team ${fixture.home_team_id}`
  const away = fixture.away_team_name ?? `Team ${fixture.away_team_id}`
  const homeStats = statistics.find(s => s.team_id === fixture.home_team_id)
  const awayStats = statistics.find(s => s.team_id === fixture.away_team_id)
  const homeScopeForm = homeTeamForm?.scopes.find(s => s.scope === 'home') ?? null
  const awayScopeForm = awayTeamForm?.scopes.find(s => s.scope === 'away') ?? null
  const eloByTeam = Object.fromEntries(leagueEloRows.map(r => [r.team_id, r.elo_overall])) as Record<number, number>
  const rankByTeam = Object.fromEntries(leagueEloRows.map(r => [r.team_id, r.rank])) as Record<number, number>
  const homeInjuries = injuries.filter(i => i.team_id === fixture.home_team_id)
  const awayInjuries = injuries.filter(i => i.team_id === fixture.away_team_id)
  const impactsByPlayerId = new Map(
    injury_impacts
      .filter(i => i.player_id != null)
      .map(i => [i.player_id as number, i])
  )

  const rows: Array<{ label: string; key: keyof FixtureStatistic }> = [
    { label: 'Erwartete Tore (xG)', key: 'expected_goals' },
    { label: 'Ballbesitz %', key: 'ball_possession' },
    { label: 'Schüsse gesamt', key: 'shots_total' },
    { label: 'Schüsse aufs Tor', key: 'shots_on_goal' },
    { label: 'Ecken', key: 'corner_kicks' },
    { label: 'Fouls', key: 'fouls' },
    { label: 'Pässe gesamt', key: 'passes_total' },
    { label: 'Passquote %', key: 'pass_accuracy' },
    { label: 'Gelbe Karten', key: 'yellow_cards' },
    { label: 'Rote Karten', key: 'red_cards' },
  ]

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-start">
        <Stack gap={2}>
          <Group gap="xs" style={{ cursor: 'pointer' }} onClick={() => navigate(`/liga/${fixture.league_id}`)}>
            <IconArrowLeft size={16} />
            <Text size="sm" c="dimmed">Zur Liga</Text>
          </Group>
          <Group gap="xs">
            <img src={leagueLogoUrl(fixture.league_id)} width={22} height={22} alt="league" />
            <Title order={2}>{fixture.league_name}</Title>
            <Badge variant="light">Spieltag {fixture.matchday ?? '–'}</Badge>
          </Group>
          <Text size="sm" c="dimmed">
            {fixture.kickoff_utc ? dayjs(fixture.kickoff_utc + 'Z').format('DD.MM.YYYY HH:mm') : '–'} · {fixture.venue_name ?? 'Unbekanntes Stadion'}
          </Text>
        </Stack>
        <Badge color="blue" variant="dot">
          {STATUS_LABELS[fixture.status_short ?? ''] ?? fixture.status_short ?? '–'}
        </Badge>
      </Group>

      <Card withBorder>
        <Group justify="space-between" align="center" wrap="nowrap">
          <Stack gap={4} align="center" style={{ minWidth: 210 }}>
            <FormLogo
              teamId={fixture.home_team_id}
              teamName={home}
              formScore={homeScopeForm?.form_score ?? null}
              trend={homeScopeForm?.form_trend ?? null}
            />
            <Text
              fw={700}
              ta="center"
              style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/team/${fixture.home_team_id}?season_year=${fixture.season_year}&league_id=${fixture.league_id}`)}
            >
              {home}
            </Text>
            <Badge size="xs" variant="light" color="indigo">
              Elo {fmtElo(homeTeamElo?.elo_overall)}
            </Badge>
            <LastFiveForm
              lastMatches={homeTeamSummary?.last_matches}
              ownElo={homeTeamElo?.elo_overall}
              eloByTeam={eloByTeam}
              rankByTeam={rankByTeam}
            />
          </Stack>
          <Text fw={800} size="xl">{fixture.home_score ?? '–'} : {fixture.away_score ?? '–'}</Text>
          <Stack gap={4} align="center" style={{ minWidth: 210 }}>
            <FormLogo
              teamId={fixture.away_team_id}
              teamName={away}
              formScore={awayScopeForm?.form_score ?? null}
              trend={awayScopeForm?.form_trend ?? null}
            />
            <Text
              fw={700}
              ta="center"
              style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/team/${fixture.away_team_id}?season_year=${fixture.season_year}&league_id=${fixture.league_id}`)}
            >
              {away}
            </Text>
            <Badge size="xs" variant="light" color="indigo">
              Elo {fmtElo(awayTeamElo?.elo_overall)}
            </Badge>
            <LastFiveForm
              lastMatches={awayTeamSummary?.last_matches}
              ownElo={awayTeamElo?.elo_overall}
              eloByTeam={eloByTeam}
              rankByTeam={rankByTeam}
            />
          </Stack>
        </Group>
      </Card>

      <Card withBorder>
          <Title order={4} mb="sm">Teamvergleich (Heim/Auswärts-Durchschnitt)</Title>
          {!homeTeamSummary || !awayTeamSummary ? (
            <Center py="md"><Loader size="sm" /></Center>
          ) : (
            <Grid gutter="md">
              <GridCol span={{ base: 12, md: 3 }}>
                <Stack gap={6}>
                  <Text fw={700}>{home} (Heim)</Text>
                  <Text size="sm">Tore pro Spiel: {fmtValue(homeTeamSummary.home_played ? homeTeamSummary.goals_for_home / homeTeamSummary.home_played : null)}</Text>
                  <Text size="sm">Gegentore pro Spiel: {fmtValue(homeTeamSummary.home_played ? homeTeamSummary.goals_against_home / homeTeamSummary.home_played : null)}</Text>
                  <Text size="sm">Schüsse pro Spiel: {fmtValue(homeTeamSummary.home_played ? homeTeamSummary.shots_total_home / homeTeamSummary.home_played : null)}</Text>
                  <Text size="sm">Schüsse aufs Tor pro Spiel: {fmtValue(homeTeamSummary.home_played ? homeTeamSummary.shots_on_goal_home / homeTeamSummary.home_played : null)}</Text>
                  <Text size="sm">Ø Ballbesitz: {fmtValue(homeTeamSummary.avg_ball_possession_home)}</Text>
                  <Text size="sm">xG pro Spiel: {fmtValue(homeTeamSummary.xg_total_home != null && homeTeamSummary.home_played ? homeTeamSummary.xg_total_home / homeTeamSummary.home_played : null)}</Text>
                </Stack>
              </GridCol>

              <GridCol span={{ base: 12, md: 3 }}>
                <Stack gap={6} align="flex-start">
                  <Group justify="space-between" align="center">
                    <Badge size="xs" color="red" variant="light">
                      Impact: {fmtValue(team_injury_impact_home)}
                    </Badge>
                    <Text fw={700}>Ausfälle {home}</Text>
                  </Group>
                  {homeInjuries.length === 0 ? (
                    <Text size="sm" c="dimmed">Keine gemeldeten Ausfälle.</Text>
                  ) : (
                    homeInjuries.map((i, idx) => {
                      const impact = i.player_id != null ? impactsByPlayerId.get(i.player_id) : undefined
                      const hasInjuryInfo = Boolean(i.injury_type || i.injury_reason)
                      return (
                        <Group key={`${i.player_id ?? 'home'}-${idx}`} gap={8} wrap="nowrap" align="flex-start">
                          <Avatar
                            src={i.player_id ? playerImageUrl(i.player_id) : undefined}
                            size={24}
                            radius="xl"
                          />
                          <Stack gap={1} style={{ flex: 1 }}>
                            <Text size="sm" fw={500}>
                              {i.player_name ?? 'Unbekannt'}
                            </Text>
                            <Badge size="xs" color={impact ? impactBadgeColor(impact.impact_bucket) : 'gray'} variant="light" w="fit-content">
                              {impact ? `${impact.impact_bucket} ${fmtValue(impact.impact_score)}` : 'Impact n/v'}
                            </Badge>
                            {hasInjuryInfo && (
                              <Text size="xs" c="dimmed">
                                {i.injury_type ?? ''}{i.injury_reason ? ` · ${i.injury_reason}` : ''}
                              </Text>
                            )}
                          </Stack>
                        </Group>
                      )
                    })
                  )}
                </Stack>
              </GridCol>

              <GridCol span={{ base: 12, md: 3 }}>
                <Stack gap={6} align="flex-end">
                  <Group justify="space-between" align="center">
                    <Text fw={700}>Ausfälle {away}</Text>
                    <Badge size="xs" color="red" variant="light">
                      Impact: {fmtValue(team_injury_impact_away)}
                    </Badge>
                  </Group>
                  {awayInjuries.length === 0 ? (
                    <Text size="sm" c="dimmed">Keine gemeldeten Ausfälle.</Text>
                  ) : (
                    awayInjuries.map((i, idx) => {
                      const impact = i.player_id != null ? impactsByPlayerId.get(i.player_id) : undefined
                      const hasInjuryInfo = Boolean(i.injury_type || i.injury_reason)
                      return (
                        <Group key={`${i.player_id ?? 'away'}-${idx}`} gap={8} wrap="nowrap" align="flex-start" w="100%" justify="flex-end">
                          <Stack gap={1} style={{ textAlign: 'right' }}>
                            <Text size="sm" fw={500}>
                              {i.player_name ?? 'Unbekannt'}
                            </Text>
                            <Badge
                              size="xs"
                              color={impact ? impactBadgeColor(impact.impact_bucket) : 'gray'}
                              variant="light"
                              ml="auto"
                              w="fit-content"
                            >
                              {impact ? `${impact.impact_bucket} ${fmtValue(impact.impact_score)}` : 'Impact n/v'}
                            </Badge>
                            {hasInjuryInfo && (
                              <Text size="xs" c="dimmed">
                                {i.injury_type ?? ''}{i.injury_reason ? ` · ${i.injury_reason}` : ''}
                              </Text>
                            )}
                          </Stack>
                          <Avatar
                            src={i.player_id ? playerImageUrl(i.player_id) : undefined}
                            size={24}
                            radius="xl"
                          />
                        </Group>
                      )
                    })
                  )}
                </Stack>
              </GridCol>

              <GridCol span={{ base: 12, md: 3 }}>
                <Stack gap={6} align="flex-end" style={{ textAlign: 'right' }}>
                  <Text fw={700}>{away} (Auswärts)</Text>
                  <Text size="sm">Tore pro Spiel: {fmtValue(awayTeamSummary.away_played ? awayTeamSummary.goals_for_away / awayTeamSummary.away_played : null)}</Text>
                  <Text size="sm">Gegentore pro Spiel: {fmtValue(awayTeamSummary.away_played ? awayTeamSummary.goals_against_away / awayTeamSummary.away_played : null)}</Text>
                  <Text size="sm">Schüsse pro Spiel: {fmtValue(awayTeamSummary.away_played ? awayTeamSummary.shots_total_away / awayTeamSummary.away_played : null)}</Text>
                  <Text size="sm">Schüsse aufs Tor pro Spiel: {fmtValue(awayTeamSummary.away_played ? awayTeamSummary.shots_on_goal_away / awayTeamSummary.away_played : null)}</Text>
                  <Text size="sm">Ø Ballbesitz: {fmtValue(awayTeamSummary.avg_ball_possession_away)}</Text>
                  <Text size="sm">xG pro Spiel: {fmtValue(awayTeamSummary.xg_total_away != null && awayTeamSummary.away_played ? awayTeamSummary.xg_total_away / awayTeamSummary.away_played : null)}</Text>
                </Stack>
              </GridCol>
            </Grid>
          )}
      </Card>

      <Card withBorder>
        <Title order={4} mb="sm">Vorhersage</Title>
        {!prediction ? (
          <Alert icon={<IconInfoCircle size={16} />} color="gray">Keine Predictiondaten vorhanden.</Alert>
        ) : (
          <Stack gap={6}>
            <Group gap="xs">
              <Badge color="indigo" variant="light">Heim: {prediction.percent_home != null ? `${prediction.percent_home}%` : '–'}</Badge>
              <Badge color="gray" variant="light">Unentschieden: {prediction.percent_draw != null ? `${prediction.percent_draw}%` : '–'}</Badge>
              <Badge color="teal" variant="light">Auswärts: {prediction.percent_away != null ? `${prediction.percent_away}%` : '–'}</Badge>
            </Group>
            <Text size="sm"><Text span fw={600}>Tendenz:</Text> {prediction.winner_name ?? '–'}{prediction.winner_comment ? ` (${prediction.winner_comment})` : ''}</Text>
            <Text size="sm"><Text span fw={600}>Tipp:</Text> {prediction.advice ?? '–'}</Text>
            <Text size="sm"><Text span fw={600}>Over/Under:</Text> {prediction.under_over ?? '–'}</Text>
            <Text size="xs" c="dimmed">
              Aktualisiert: {prediction.fetched_at ? dayjs(prediction.fetched_at + 'Z').format('DD.MM.YYYY HH:mm') : '–'}
            </Text>
          </Stack>
        )}
      </Card>

      <Card withBorder>
        <Title order={4} mb="sm">Torwahrscheinlichkeit (gewichtet)</Title>
        {!goal_probability_home || !goal_probability_away ? (
          <Alert icon={<IconInfoCircle size={16} />} color="gray">
            Keine Torwahrscheinlichkeitsdaten vorhanden.
          </Alert>
        ) : (
          <Grid gutter="md">
            <GridCol span={{ base: 12, md: 6 }}>
              <Stack gap={4}>
                <Text fw={700}>{home}</Text>
                <Text size="sm">≥ 1 Tor: {fmtPct(goal_probability_home.p_ge_1_goal)}</Text>
                <Text size="sm">≥ 2 Tore: {fmtPct(goal_probability_home.p_ge_2_goals)}</Text>
                <Text size="sm">≥ 3 Tore: {fmtPct(goal_probability_home.p_ge_3_goals)}</Text>
                <Text size="xs" c="dimmed">
                  λ: {fmtValue(goal_probability_home.lambda_weighted)} ·
                  Confidence: {fmtPct(goal_probability_home.confidence)} ·
                  Sample: {goal_probability_home.sample_size}
                </Text>
              </Stack>
            </GridCol>
            <GridCol span={{ base: 12, md: 6 }}>
              <Stack gap={4} align="flex-end" style={{ textAlign: 'right' }}>
                <Text fw={700}>{away}</Text>
                <Text size="sm">≥ 1 Tor: {fmtPct(goal_probability_away.p_ge_1_goal)}</Text>
                <Text size="sm">≥ 2 Tore: {fmtPct(goal_probability_away.p_ge_2_goals)}</Text>
                <Text size="sm">≥ 3 Tore: {fmtPct(goal_probability_away.p_ge_3_goals)}</Text>
                <Text size="xs" c="dimmed">
                  λ: {fmtValue(goal_probability_away.lambda_weighted)} ·
                  Confidence: {fmtPct(goal_probability_away.confidence)} ·
                  Sample: {goal_probability_away.sample_size}
                </Text>
              </Stack>
            </GridCol>
          </Grid>
        )}
      </Card>

      <Card withBorder>
        <Title order={4} mb="sm">Potenzielle Anzahl an Gegentoren (gewichtet)</Title>
        {!concede_probability_home || !concede_probability_away ? (
          <Alert icon={<IconInfoCircle size={16} />} color="gray">
            Keine Gegentorwahrscheinlichkeitsdaten vorhanden.
          </Alert>
        ) : (
          <Grid gutter="md">
            <GridCol span={{ base: 12, md: 6 }}>
              <Stack gap={4}>
                <Text fw={700}>{home}</Text>
                <Text size="sm">≥ 1 Gegentor: {fmtPct(concede_probability_home.p_ge_1_goal)}</Text>
                <Text size="sm">≥ 2 Gegentore: {fmtPct(concede_probability_home.p_ge_2_goals)}</Text>
                <Text size="sm">≥ 3 Gegentore: {fmtPct(concede_probability_home.p_ge_3_goals)}</Text>
                <Text size="xs" c="dimmed">
                  λ Gegner: {fmtValue(concede_probability_home.lambda_weighted)} ·
                  Confidence: {fmtPct(concede_probability_home.confidence)} ·
                  Sample: {concede_probability_home.sample_size}
                </Text>
              </Stack>
            </GridCol>
            <GridCol span={{ base: 12, md: 6 }}>
              <Stack gap={4} align="flex-end" style={{ textAlign: 'right' }}>
                <Text fw={700}>{away}</Text>
                <Text size="sm">≥ 1 Gegentor: {fmtPct(concede_probability_away.p_ge_1_goal)}</Text>
                <Text size="sm">≥ 2 Gegentore: {fmtPct(concede_probability_away.p_ge_2_goals)}</Text>
                <Text size="sm">≥ 3 Gegentore: {fmtPct(concede_probability_away.p_ge_3_goals)}</Text>
                <Text size="xs" c="dimmed">
                  λ Gegner: {fmtValue(concede_probability_away.lambda_weighted)} ·
                  Confidence: {fmtPct(concede_probability_away.confidence)} ·
                  Sample: {concede_probability_away.sample_size}
                </Text>
              </Stack>
            </GridCol>
          </Grid>
        )}
      </Card>

      <Card withBorder>
        <Title order={4} mb="sm">Globale Match-Werte (+0,5 / +1,5 Tore)</Title>
        {!match_goal_lines ? (
          <Alert icon={<IconInfoCircle size={16} />} color="gray">
            Keine kombinierten Match-Werte vorhanden.
          </Alert>
        ) : (
          <Grid gutter="md">
            <GridCol span={{ base: 12, md: 6 }}>
              <Stack gap={4}>
                <Text fw={700}>{home}</Text>
                <Text size="sm">+0,5 Tore: {fmtPct(match_goal_lines.home.plus_0_5)}</Text>
                <Text size="sm">+1,5 Tore: {fmtPct(match_goal_lines.home.plus_1_5)}</Text>
                <Text size="xs" c="dimmed">
                  λ Basis: {fmtValue(match_goal_lines.home.lambda_base)} ·
                  λ Final: {fmtValue(match_goal_lines.home.lambda_final)}
                </Text>
                <Text size="xs" c="dimmed">
                  Faktoren: Heim {fmtValue(match_goal_lines.home.factors.home_advantage)} ·
                  Elo {fmtValue(match_goal_lines.home.factors.elo)} ·
                  Form {fmtValue(match_goal_lines.home.factors.form)}
                </Text>
              </Stack>
            </GridCol>
            <GridCol span={{ base: 12, md: 6 }}>
              <Stack gap={4} align="flex-end" style={{ textAlign: 'right' }}>
                <Text fw={700}>{away}</Text>
                <Text size="sm">+0,5 Tore: {fmtPct(match_goal_lines.away.plus_0_5)}</Text>
                <Text size="sm">+1,5 Tore: {fmtPct(match_goal_lines.away.plus_1_5)}</Text>
                <Text size="xs" c="dimmed">
                  λ Basis: {fmtValue(match_goal_lines.away.lambda_base)} ·
                  λ Final: {fmtValue(match_goal_lines.away.lambda_final)}
                </Text>
                <Text size="xs" c="dimmed">
                  Faktoren: Heim {fmtValue(match_goal_lines.away.factors.home_advantage)} ·
                  Elo {fmtValue(match_goal_lines.away.factors.elo)} ·
                  Form {fmtValue(match_goal_lines.away.factors.form)}
                </Text>
              </Stack>
            </GridCol>
          </Grid>
        )}
      </Card>

      <Grid gutter="md">
        <GridCol span={{ base: 12, md: 6 }}>
          <Card withBorder>
            <Title order={4} mb="sm">Team-Statistiken</Title>
            {statistics.length === 0 ? (
              <Alert icon={<IconInfoCircle size={16} />} color="gray">Keine Statistikdaten vorhanden.</Alert>
            ) : (
              <Stack gap="sm">
                {rows.map(row => (
                  <StatRow
                    key={row.key}
                    label={row.label}
                    home={statValue(homeStats, row.key)}
                    away={statValue(awayStats, row.key)}
                  />
                ))}
              </Stack>
            )}
          </Card>
        </GridCol>

        <GridCol span={{ base: 12, md: 6 }}>
          <Card withBorder>
            <Title order={4} mb="sm">Match-Events</Title>
            {events.length === 0 ? (
              <Alert icon={<IconInfoCircle size={16} />} color="gray">Keine Eventdaten vorhanden.</Alert>
            ) : (
              <Table verticalSpacing="xs" fz="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th w={70}>Minute</Table.Th>
                    <Table.Th w={110}>Team</Table.Th>
                    <Table.Th>Event</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {events.map((ev, idx) => (
                    <Table.Tr key={`${ev.id}-${idx}`}>
                      <Table.Td>{fmtMinute(ev.elapsed, ev.elapsed_extra)}</Table.Td>
                      <Table.Td>
                        <Text size="xs" c="dimmed">{ev.team_name ?? ev.team_id}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" fw={600}>
                          {translateEventDetail(ev.detail) ?? translateEventType(ev.event_type) ?? 'Ereignis'}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {ev.player_name ?? 'Unbekannt'}
                          {ev.assist_name ? ` · Vorlage: ${ev.assist_name}` : ''}
                          {ev.comments ? ` · ${ev.comments}` : ''}
                        </Text>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Card>
        </GridCol>
      </Grid>

      <Divider />
      <Text size="xs" c="dimmed">Quelle: lokal gespeicherte Fixture-, Prediction-, Injury-, Statistics- und Event-Daten.</Text>
    </Stack>
  )
}

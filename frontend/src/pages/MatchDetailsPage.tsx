import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  Center,
  Divider,
  Grid,
  GridCol,
  Group,
  Loader,
  Paper,
  Progress,
  RingProgress,
  SegmentedControl,
  Stack,
  Table,
  Tabs,
  Text,
  Title,
  Tooltip,
} from '@mantine/core'
import { RadarChart } from '@mantine/charts'
import { IconArrowLeft, IconBrain, IconInfoCircle } from '@tabler/icons-react'
import { useMutation, useQuery } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { fixturesApi, leaguesApi, teamsApi } from '../api'
import type { FixtureDetails, FixtureStatistic, TeamLastMatch, TeamSummary } from '../types'
import { leagueLogoUrl, playerImageUrl, STATUS_LABELS, teamLogoUrl } from '../types'

// ─── Formatters ───────────────────────────────────────────────────────────────

const fmtMinute = (e: number | null, x: number | null) =>
  e == null ? '–' : x != null ? `${e}+${x}'` : `${e}'`

const fmtV = (v: number | null | undefined, d = 1): string => {
  if (v == null) return '–'
  if (d === 0 || Number.isInteger(v)) return String(Math.round(v))
  return v.toFixed(d).replace('.', ',')
}

const fmtPct = (v: number | null | undefined, already = false): string => {
  if (v == null) return '–'
  return `${((already ? v : v * 100)).toFixed(1).replace('.', ',')} %`
}

const statV = (s: FixtureStatistic | undefined, k: keyof FixtureStatistic): number | null => {
  const v = s?.[k]; return typeof v === 'number' ? v : null
}

// ─── Event labels ─────────────────────────────────────────────────────────────

const DETAIL_MAP: Record<string, string> = {
  'Normal Goal': 'Tor', 'Own Goal': 'Eigentor', Penalty: 'Elfmeter',
  'Missed Penalty': 'Elfmeter verschossen', 'Yellow Card': 'Gelbe Karte',
  'Red Card': 'Rote Karte', 'Second Yellow card': 'Gelb-Rot',
}
const txDetail = (v: string | null) => {
  if (!v) return null
  if (v.startsWith('Substitution')) return 'Wechsel'
  return DETAIL_MAP[v] ?? v
}
const txType = (v: string | null) =>
  v ? ({ Goal: 'Tor', Card: 'Karte', subst: 'Wechsel', Var: 'VAR' }[v] ?? v) : null

// ─── Compact stat row ─────────────────────────────────────────────────────────
// Single-line: [hVal] [━━━━━━━━░░░░] [aVal]  label

function CRow({ label, home, away }: { label: string; home: number | null; away: number | null }) {
  const a = home ?? 0, b = away ?? 0, total = a + b
  const pct = total > 0 ? Math.round(a / total * 100) : 50
  const fmt = (v: number | null) => v == null ? '–' : Number.isInteger(v) ? String(v) : v.toFixed(1)
  return (
    <Group gap={6} wrap="nowrap" align="center" py={1}>
      <Text size="xs" fw={700} w={30} ta="right" c="blue">{fmt(home)}</Text>
      <Progress.Root size={6} style={{ flex: 1 }}>
        <Progress.Section value={pct} color="blue.5" />
        <Progress.Section value={100 - pct} color="teal.5" />
      </Progress.Root>
      <Text size="xs" fw={700} w={30} c="teal">{fmt(away)}</Text>
      <Text size="xs" c="dimmed" w={110} ta="right" truncate>{label}</Text>
    </Group>
  )
}

// ─── Radar helpers ────────────────────────────────────────────────────────────

const norm = (v: number | null, max: number) =>
  v == null ? 0 : Math.min(100, Math.max(0, Math.round(v / max * 100)))

// Season-profile radar: 6 axes normalized 0-100
function buildTeamRadar(
  hs: TeamSummary | undefined, as_: TeamSummary | undefined,
  hPlayed: number, aPlayed: number,
) {
  if (!hs || !as_) return null
  const hGf = hs.goals_for / (hPlayed || 1)
  const aGf = as_.goals_for / (aPlayed || 1)
  const hGa = hs.goals_against / (hPlayed || 1)
  const aGa = as_.goals_against / (aPlayed || 1)
  const hXG = hs.xg_total != null ? hs.xg_total / (hPlayed || 1) : null
  const aXG = as_.xg_total != null ? as_.xg_total / (aPlayed || 1) : null
  const hSoT = hs.shots_on_goal / (hPlayed || 1)
  const aSoT = as_.shots_on_goal / (aPlayed || 1)
  return [
    { axis: 'Tore', home: norm(hGf, 3.5), away: norm(aGf, 3.5) },
    { axis: 'xG', home: norm(hXG, 2.5), away: norm(aXG, 2.5) },
    { axis: 'Schüsse', home: norm(hSoT, 8), away: norm(aSoT, 8) },
    { axis: 'Ballbesitz', home: norm(hs.avg_ball_possession, 75), away: norm(as_.avg_ball_possession, 75) },
    { axis: 'Passquote', home: norm(hs.pass_accuracy_pct, 95), away: norm(as_.pass_accuracy_pct, 95) },
    { axis: 'Defensiv', home: Math.max(0, 100 - norm(hGa, 3.5)), away: Math.max(0, 100 - norm(aGa, 3.5)) },
  ]
}

// Match-stats radar from fixture_statistics
function buildMatchRadar(
  hStat: FixtureStatistic | undefined, aStat: FixtureStatistic | undefined,
) {
  if (!hStat && !aStat) return null
  return [
    { axis: 'xG', home: norm(statV(hStat, 'expected_goals'), 3), away: norm(statV(aStat, 'expected_goals'), 3) },
    { axis: 'Schüsse', home: norm(statV(hStat, 'shots_total'), 25), away: norm(statV(aStat, 'shots_total'), 25) },
    { axis: 'SaT', home: norm(statV(hStat, 'shots_on_goal'), 10), away: norm(statV(aStat, 'shots_on_goal'), 10) },
    { axis: 'Ballbesitz', home: norm(statV(hStat, 'ball_possession'), 80), away: norm(statV(aStat, 'ball_possession'), 80) },
    { axis: 'Pässe', home: norm(statV(hStat, 'passes_total'), 700), away: norm(statV(aStat, 'passes_total'), 700) },
    { axis: 'Ecken', home: norm(statV(hStat, 'corner_kicks'), 12), away: norm(statV(aStat, 'corner_kicks'), 12) },
  ]
}

const RADAR_SERIES = [
  { name: 'home', color: 'blue.6', opacity: 0.15 },
  { name: 'away', color: 'teal.6', opacity: 0.15 },
]

// ─── Shared helpers ───────────────────────────────────────────────────────────

function impactColor(b: string | null) {
  return b === 'kritisch' ? 'red' : b === 'hoch' ? 'orange' : b === 'mittel' ? 'yellow' : 'gray'
}
function resColor(c: string) { return c === 'W' ? 'green' : c === 'D' ? 'yellow' : c === 'L' ? 'red' : 'gray' }
function resLabel(c: string) { return c === 'W' ? 'S' : c === 'D' ? 'U' : c === 'L' ? 'N' : c }

function qualityLabel(res: string | null | undefined, own?: number, opp?: number) {
  if (!res || own == null || opp == null) return ''
  const d = own - opp
  if (res === 'W') return d <= -60 ? 'Starker Sieg' : d >= 60 ? 'Pflichtsieg' : 'Solider Sieg'
  if (res === 'D') return d <= -60 ? 'Starkes Remis' : d >= 60 ? 'Enttäuschendes Remis' : 'Ordentliches Remis'
  return d <= -60 ? 'Akzeptable Niederlage' : d >= 60 ? 'Schwache Niederlage' : 'Normale Niederlage'
}

function FormPills({ matches, ownElo, eloByTeam, rankByTeam }: {
  matches: TeamLastMatch[] | undefined
  ownElo?: number
  eloByTeam: Record<number, number>
  rankByTeam: Record<number, number>
}) {
  const m = (matches ?? []).slice(0, 5)
  if (!m.length) return <Text size="xs" c="dimmed">n/v</Text>
  return (
    <Group gap={3} wrap="nowrap">
      {m.map((x, i) => {
        const c = x.result ?? '-'
        const oppElo = eloByTeam[x.opponent_team_id]
        const score = x.goals_for != null ? `${x.goals_for}:${x.goals_against}` : '–'
        const rank = rankByTeam[x.opponent_team_id]
        return (
          <Tooltip key={`${x.fixture_id}-${i}`} multiline w={260} label={
            `${x.is_home ? 'H' : 'A'} vs ${x.opponent_team_name} · ${score}` +
            (oppElo ? ` · Elo ${oppElo.toFixed(0)}${rank ? ` #${rank}` : ''}` : '') +
            (qualityLabel(x.result, ownElo, oppElo) ? ` · ${qualityLabel(x.result, ownElo, oppElo)}` : '')
          }>
            <Badge size="xs" color={resColor(c)} variant="filled">{resLabel(c)}</Badge>
          </Tooltip>
        )
      })}
    </Group>
  )
}

function FormLogo({ teamId, teamName, score, trend }: {
  teamId: number; teamName: string; score: number | null; trend: string | null
}) {
  const color = score == null ? 'gray' : score >= 70 ? 'green' : score >= 40 ? 'yellow' : 'red'
  return (
    <Tooltip label={`Form: ${score?.toFixed(1) ?? 'n/v'}${trend ? ` · ${trend}` : ''}`} position="bottom">
      <RingProgress size={80} thickness={4} roundCaps sections={[{ value: score ?? 0, color }]}
        label={<img src={teamLogoUrl(teamId)} width={42} height={42} alt={teamName}
          style={{ display: 'block', margin: '0 auto', objectFit: 'contain' }} />}
      />
    </Tooltip>
  )
}

// ─── Tab: Teamvergleich ───────────────────────────────────────────────────────

const pg = (n: number | null | undefined, d: number | undefined) =>
  n == null || !d ? null : n / d

function TeamVergleichTab({ homeId, awayId, hs, as_, h2h, homeName, awayName }: {
  homeId: number; awayId: number
  hs: TeamSummary | undefined; as_: TeamSummary | undefined
  h2h: FixtureDetails['h2h']
  homeName: string; awayName: string
}) {
  const [scope, setScope] = useState<'g' | 'k'>('k')
  const s = scope === 'g'

  const hP = s ? hs?.played : hs?.home_played
  const aP = s ? as_?.played : as_?.away_played

  const hGf  = s ? pg(hs?.goals_for, hs?.played) : pg(hs?.goals_for_home, hs?.home_played)
  const hGa  = s ? pg(hs?.goals_against, hs?.played) : pg(hs?.goals_against_home, hs?.home_played)
  const hXG  = s ? pg(hs?.xg_total, hs?.played) : pg(hs?.xg_total_home, hs?.home_played)
  const hPos = s ? hs?.avg_ball_possession : hs?.avg_ball_possession_home
  const hSh  = s ? pg(hs?.shots_total, hs?.played) : pg(hs?.shots_total_home, hs?.home_played)
  const hSoT = s ? pg(hs?.shots_on_goal, hs?.played) : pg(hs?.shots_on_goal_home, hs?.home_played)
  const hCrn = s ? pg(hs?.corners, hs?.played) : pg(hs?.corners_home, hs?.home_played)
  const hFl  = s ? pg(hs?.fouls, hs?.played) : pg(hs?.fouls_home, hs?.home_played)
  const hPPG = hP ? ((s ? hs?.points : hs?.home_points) ?? null) : null
  const hPPGv = hPPG != null && hP ? hPPG / hP : null

  const aGf  = s ? pg(as_?.goals_for, as_?.played) : pg(as_?.goals_for_away, as_?.away_played)
  const aGa  = s ? pg(as_?.goals_against, as_?.played) : pg(as_?.goals_against_away, as_?.away_played)
  const aXG  = s ? pg(as_?.xg_total, as_?.played) : pg(as_?.xg_total_away, as_?.away_played)
  const aPos = s ? as_?.avg_ball_possession : as_?.avg_ball_possession_away
  const aSh  = s ? pg(as_?.shots_total, as_?.played) : pg(as_?.shots_total_away, as_?.away_played)
  const aSoT = s ? pg(as_?.shots_on_goal, as_?.played) : pg(as_?.shots_on_goal_away, as_?.away_played)
  const aCrn = s ? pg(as_?.corners, as_?.played) : pg(as_?.corners_away, as_?.away_played)
  const aFl  = s ? pg(as_?.fouls, as_?.played) : pg(as_?.fouls_away, as_?.away_played)
  const aPPG = aP ? ((s ? as_?.points : as_?.away_points) ?? null) : null
  const aPPGv = aPPG != null && aP ? aPPG / aP : null

  const radarData = buildTeamRadar(
    hs, as_,
    s ? (hs?.played ?? 0) : (hs?.home_played ?? 0),
    s ? (as_?.played ?? 0) : (as_?.away_played ?? 0),
  )

  return (
    <Stack gap="sm">
      {/* Controls */}
      <Group justify="space-between" align="center" wrap="wrap" gap="xs">
        <Group gap={6}>
          <img src={teamLogoUrl(homeId)} width={16} height={16} style={{ objectFit: 'contain' }} alt="" />
          <Text size="xs" fw={600} c="blue">{homeName}</Text>
          <Text size="xs" c="dimmed">vs</Text>
          <Text size="xs" fw={600} c="teal">{awayName}</Text>
          <img src={teamLogoUrl(awayId)} width={16} height={16} style={{ objectFit: 'contain' }} alt="" />
        </Group>
        <SegmentedControl size="xs" value={scope} onChange={v => setScope(v as 'g' | 'k')}
          data={[{ label: 'Gesamt', value: 'g' }, { label: 'Heim / Auswärts', value: 'k' }]} />
      </Group>

      {scope === 'k' && (
        <Group gap={6}>
          <Badge size="xs" color="blue" variant="light">{homeName}: Heim ({hs?.home_played ?? 0} Sp.)</Badge>
          <Badge size="xs" color="teal" variant="light">{awayName}: Auswärts ({as_?.away_played ?? 0} Sp.)</Badge>
        </Group>
      )}

      {!hs || !as_ ? <Center py="sm"><Loader size="sm" /></Center> : (
        <Grid gutter="md" align="flex-start">
          {/* Radar */}
          <GridCol span={{ base: 12, md: 7 }}>
            {radarData ? (
              <RadarChart h={220} data={radarData} dataKey="axis" withLegend={false}
                series={RADAR_SERIES}
              />
            ) : (
              <Center h={220}><Text size="xs" c="dimmed">Keine Daten für Radar</Text></Center>
            )}
          </GridCol>

          {/* Compact stat list */}
          <GridCol span={{ base: 12, md: 5 }}>
            <Stack gap={2} pt={4}>
              <CRow label="Punkte/Sp"     home={hPPGv}          away={aPPGv} />
              <CRow label="Tore/Sp"       home={hGf}            away={aGf} />
              <CRow label="Gegentore/Sp"  home={hGa}            away={aGa} />
              <CRow label="xG/Sp"         home={hXG}            away={aXG} />
              <CRow label="Ballbesitz %"  home={hPos ?? null}   away={aPos ?? null} />
              <CRow label="Schüsse/Sp"    home={hSh}            away={aSh} />
              <CRow label="SaT/Sp"        home={hSoT}           away={aSoT} />
              <CRow label="Ecken/Sp"      home={hCrn}           away={aCrn} />
              <CRow label="Fouls/Sp"      home={hFl}            away={aFl} />
              <CRow label="Passquote %"   home={hs.pass_accuracy_pct ?? null} away={as_.pass_accuracy_pct ?? null} />
            </Stack>
          </GridCol>
        </Grid>
      )}

      {/* H2H */}
      {h2h && (
        <>
          <Divider label={`H2H · ${h2h.matches_total} Spiele`} labelPosition="center" my={2} />
          <Grid gutter="xs" align="center">
            <GridCol span={3}>
              <Stack gap={0} align="center">
                <Text fw={800} size="lg" c="blue">{h2h.home_wins}</Text>
                <Text size="xs" c="dimmed">S {homeName.split(' ')[0]}</Text>
              </Stack>
            </GridCol>
            <GridCol span={6}>
              <Stack gap={4}>
                <Progress.Root size={12} radius="xl">
                  <Tooltip label={`${homeName} ${fmtPct(h2h.home_win_pct)}`}>
                    <Progress.Section value={h2h.home_win_pct * 100} color="blue" />
                  </Tooltip>
                  <Tooltip label={`Remis ${fmtPct(h2h.draw_pct)}`}>
                    <Progress.Section value={h2h.draw_pct * 100} color="gray" />
                  </Tooltip>
                  <Tooltip label={`${awayName} ${fmtPct(h2h.away_win_pct)}`}>
                    <Progress.Section value={h2h.away_win_pct * 100} color="teal" />
                  </Tooltip>
                </Progress.Root>
                <Group gap="xs" justify="center">
                  <Badge size="xs" color={h2h.btts_rate > .5 ? 'green' : 'gray'} variant="light">
                    BTTS {fmtPct(h2h.btts_rate)}
                  </Badge>
                  <Badge size="xs" color={h2h.over_25_rate > .5 ? 'green' : 'gray'} variant="light">
                    Ü2,5 {fmtPct(h2h.over_25_rate)}
                  </Badge>
                  <Badge size="xs" color="gray" variant="outline">
                    Ø {fmtV(h2h.avg_total_goals)} Tore
                  </Badge>
                </Group>
              </Stack>
            </GridCol>
            <GridCol span={3}>
              <Stack gap={0} align="center">
                <Text fw={800} size="lg" c="teal">{h2h.away_wins}</Text>
                <Text size="xs" c="dimmed">S {awayName.split(' ')[0]}</Text>
              </Stack>
            </GridCol>
          </Grid>
        </>
      )}
    </Stack>
  )
}

// ─── Pattern-Schnellbewertung ─────────────────────────────────────────────────

interface PredLine {
  label: string
  value: string          // the prediction text
  prob: number           // probability of the predicted outcome (0-1)
  isJa: boolean          // true=Ja/positive, false=Nein/negative
}

function confColor(prob: number, isJa: boolean): string {
  if (!isJa) return 'gray'
  if (prob >= 0.70) return 'green'
  if (prob >= 0.58) return 'yellow'
  if (prob >= 0.52) return 'orange'
  return 'orange' // borderline Ja — still orange but value text will say "Tendenz"
}

function SchnellbewertungCard({ mrp, sl, gph, gpa, homeName, awayName }: {
  mrp: FixtureDetails['match_result_probability']
  sl:  FixtureDetails['scoreline_distribution']
  gph: FixtureDetails['goal_probability_home']
  gpa: FixtureDetails['goal_probability_away']
  homeName: string
  awayName: string
}) {
  if (!mrp && !sl && !gph) return null

  // Prefer MRP, fall back to scoreline_distribution for probabilities
  const p1   = mrp?.p_home_win ?? sl?.p_home_win ?? null
  const pX   = mrp?.p_draw     ?? sl?.p_draw     ?? null
  const p2   = mrp?.p_away_win ?? sl?.p_away_win ?? null
  const pBtts = mrp?.p_btts ?? sl?.p_btts ?? null
  const pO15  = mrp?.p_over_15 ?? sl?.p_over_15 ?? null
  const pO25  = mrp?.p_over_25 ?? sl?.p_over_25 ?? null

  // Über 0,5: 1 - P(0 goals total) ≈ 1 - (1-p_ge1_home)*(1-p_ge1_away)
  const pO05: number | null = (() => {
    if (gph && gpa) return 1 - (1 - gph.p_ge_1_goal) * (1 - gpa.p_ge_1_goal)
    if (sl) {
      // Poisson: P(0) = e^-lambda
      const ph0 = Math.exp(-sl.lambda_home)
      const pa0 = Math.exp(-sl.lambda_away)
      return 1 - ph0 * pa0
    }
    return null
  })()

  // Helper: binary market label with threshold + "Tendenz" zone
  const binLine = (label: string, p: number, threshold = 0.50, tendenzZone = 0.57): PredLine => {
    const ja = p >= threshold
    const prob = ja ? p : 1 - p
    // "Tendenz Ja" for barely-above-threshold predictions
    const value = ja
      ? (p < tendenzZone ? 'Tendenz Ja' : 'Ja')
      : (1 - p < tendenzZone ? 'Tendenz Nein' : 'Nein')
    return { label, value, prob, isJa: ja }
  }

  const lines: PredLine[] = []

  // Ergebnis: no threshold — always show the most likely outcome.
  // Probability shown is what the model assigns to that outcome.
  if (p1 != null && pX != null && p2 != null) {
    const probs = [p1, pX, p2]
    const idx = probs.indexOf(Math.max(...probs))
    const outcome = idx === 0
      ? `Sieg ${homeName.split(' ')[0]}`
      : idx === 1 ? 'Unentschieden'
      : `Sieg ${awayName.split(' ')[0]}`
    const score = sl?.most_likely_score ? ` (${sl.most_likely_score})` : ''
    lines.push({ label: 'Ergebnis', value: outcome + score, prob: probs[idx], isJa: true })
  }

  // Doppelte Chance: always show best option — threshold irrelevant by construction.
  if (p1 != null && pX != null && p2 != null) {
    const dc = [{ key: '1X', p: p1 + pX }, { key: 'X2', p: pX + p2 }, { key: '12', p: p1 + p2 }]
    const best = dc.reduce((a, b) => b.p > a.p ? b : a)
    lines.push({ label: 'Doppelte Chance', value: best.key, prob: best.p, isJa: true })
  }

  // BTTS — threshold 50 %, "Tendenz" zone 50–57 %
  if (pBtts != null) lines.push(binLine('Beide treffen (BTTS)', pBtts, 0.50, 0.57))

  // Team trifft — threshold 50 %, rarely borderline for strong teams
  if (gph) lines.push(binLine(`${homeName.split(' ')[0]} trifft`, gph.p_ge_1_goal, 0.50, 0.60))
  if (gpa) lines.push(binLine(`${awayName.split(' ')[0]} trifft`, gpa.p_ge_1_goal, 0.50, 0.60))

  // Über 0,5 — almost always > 90 %; threshold raised to 85 % so the bar
  // actually carries information (a "Nein" here would be extraordinary).
  if (pO05 != null) lines.push(binLine('Über 0,5', pO05, 0.85, 0.93))

  // Über 1,5 — raise threshold slightly to 55 % to avoid noise
  if (pO15 != null) lines.push(binLine('Über 1,5', pO15, 0.55, 0.65))

  // Über 2,5 — classic 50 % swing market
  if (pO25 != null) lines.push(binLine('Über 2,5', pO25, 0.50, 0.58))

  if (!lines.length) return null

  return (
    <Card withBorder p="sm">
      <Text size="xs" fw={700} c="dimmed" mb={8} tt="uppercase" lts={0.5}>Pattern-Schnellbewertung</Text>
      <Stack gap={5}>
        {lines.map(({ label, value, prob, isJa }) => {
          const color = confColor(prob, isJa)
          return (
            <Group key={label} gap={8} wrap="nowrap" align="center">
              {/* Label */}
              <Text size="xs" c="dimmed" w={160} style={{ flexShrink: 0 }}>{label}</Text>
              {/* Prediction badge */}
              <Badge
                size="sm"
                color={color}
                variant={isJa ? 'filled' : 'light'}
                w={120}
                style={{ flexShrink: 0, textAlign: 'center', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
              >
                {value}
              </Badge>
              {/* Probability bar */}
              <Progress
                value={prob * 100}
                color={color}
                size={6}
                style={{ flex: 1 }}
              />
              {/* % */}
              <Text size="xs" c={color === 'gray' ? 'dimmed' : color} fw={600} w={36} ta="right" style={{ flexShrink: 0 }}>
                {(prob * 100).toFixed(0)} %
              </Text>
            </Group>
          )
        })}
      </Stack>
    </Card>
  )
}

// ─── Tab: Prognose ────────────────────────────────────────────────────────────

function PrognoseTab({ data, homeName, awayName }: {
  data: FixtureDetails; homeName: string; awayName: string
}) {
  const { prediction: pred, match_result_probability: mrp, scoreline_distribution: sl,
    goal_probability_home: gph, goal_probability_away: gpa,
    goal_timing_home: gth, goal_timing_away: gta,
    home_advantage_home: hah, home_advantage_away: haa,
    value_bets, pattern_evaluation: pe } = data

  return (
    <Stack gap="sm">
      {/* Schnellbewertung */}
      <SchnellbewertungCard mrp={mrp} sl={sl} gph={gph} gpa={gpa} homeName={homeName} awayName={awayName} />

      {/* API-Football vs Pattern side by side */}
      <Grid gutter="sm">
        <GridCol span={{ base: 12, md: 6 }}>
          <Card withBorder p="sm" h="100%">
            <Group gap={6} mb={8}>
              <Badge size="xs" color="gray" variant="light">API-Football</Badge>
            </Group>
            {!pred
              ? <Text size="xs" c="dimmed">Keine Prediction.</Text>
              : <Stack gap={6}>
                  <Stack gap={3}>
                    <Text size="xs" c="dimmed">1 / X / 2</Text>
                    <Progress.Root size={18} radius="xl">
                      <Tooltip label={`${homeName}: ${pred.percent_home ?? '–'}%`}>
                        <Progress.Section value={pred.percent_home ?? 0} color="blue">
                          <Progress.Label fz={10}>{pred.percent_home ?? '–'}%</Progress.Label>
                        </Progress.Section>
                      </Tooltip>
                      <Tooltip label={`Remis: ${pred.percent_draw ?? '–'}%`}>
                        <Progress.Section value={pred.percent_draw ?? 0} color="gray">
                          <Progress.Label fz={10}>{pred.percent_draw ?? '–'}%</Progress.Label>
                        </Progress.Section>
                      </Tooltip>
                      <Tooltip label={`${awayName}: ${pred.percent_away ?? '–'}%`}>
                        <Progress.Section value={pred.percent_away ?? 0} color="teal">
                          <Progress.Label fz={10}>{pred.percent_away ?? '–'}%</Progress.Label>
                        </Progress.Section>
                      </Tooltip>
                    </Progress.Root>
                  </Stack>
                  <Group gap={4} wrap="wrap">
                    {pred.winner_name && <Text size="xs"><Text span c="dimmed">Tendenz: </Text>{pred.winner_name}</Text>}
                    {pred.advice && <Text size="xs"><Text span c="dimmed">Tipp: </Text>{pred.advice}</Text>}
                    {pred.under_over && <Badge size="xs" color="indigo" variant="light">{pred.under_over}</Badge>}
                  </Group>
                  {pred.fetched_at && <Text size="xs" c="dimmed">Stand: {dayjs(pred.fetched_at + 'Z').format('DD.MM.YY')}</Text>}
                </Stack>
            }
          </Card>
        </GridCol>

        <GridCol span={{ base: 12, md: 6 }}>
          <Card withBorder p="sm" h="100%">
            <Group gap={6} mb={8}>
              <Badge size="xs" color="indigo" variant="light">Pattern-Modell</Badge>
              {mrp && <Badge size="xs" color="gray" variant="outline">Conf. {fmtPct(mrp.confidence)}</Badge>}
            </Group>
            {!mrp && !sl && !gph
              ? <Text size="xs" c="dimmed">Keine Pattern-Vorhersage.</Text>
              : <Stack gap={6}>
                  {mrp && (
                    <Stack gap={3}>
                      <Text size="xs" c="dimmed">1 / X / 2</Text>
                      <Progress.Root size={18} radius="xl">
                        <Tooltip label={`${homeName}: ${fmtPct(mrp.p_home_win)}`}>
                          <Progress.Section value={mrp.p_home_win * 100} color="blue">
                            <Progress.Label fz={10}>{fmtPct(mrp.p_home_win)}</Progress.Label>
                          </Progress.Section>
                        </Tooltip>
                        <Tooltip label={`Remis: ${fmtPct(mrp.p_draw)}`}>
                          <Progress.Section value={mrp.p_draw * 100} color="gray">
                            <Progress.Label fz={10}>{fmtPct(mrp.p_draw)}</Progress.Label>
                          </Progress.Section>
                        </Tooltip>
                        <Tooltip label={`${awayName}: ${fmtPct(mrp.p_away_win)}`}>
                          <Progress.Section value={mrp.p_away_win * 100} color="teal">
                            <Progress.Label fz={10}>{fmtPct(mrp.p_away_win)}</Progress.Label>
                          </Progress.Section>
                        </Tooltip>
                      </Progress.Root>
                      {mrp.elo_home_prob != null && (
                        <Text size="xs" c="dimmed">Elo-Basis: {fmtPct(mrp.elo_home_prob)} / {fmtPct(mrp.elo_away_prob)}</Text>
                      )}
                    </Stack>
                  )}
                  {sl && (
                    <Group gap={4} wrap="wrap">
                      <Badge size="sm" color="indigo">{sl.most_likely_score ?? '–'} ({fmtPct(sl.most_likely_score_prob)})</Badge>
                      <Badge size="xs" color={sl.p_btts > .5 ? 'green' : 'gray'} variant="light">BTTS {fmtPct(sl.p_btts)}</Badge>
                      <Badge size="xs" color={sl.p_over_25 > .5 ? 'green' : 'gray'} variant="light">Ü2,5 {fmtPct(sl.p_over_25)}</Badge>
                      <Badge size="xs" color={sl.p_over_15 > .7 ? 'green' : 'gray'} variant="light">Ü1,5 {fmtPct(sl.p_over_15)}</Badge>
                      <Badge size="xs" color={sl.p_over_35 > .4 ? 'green' : 'gray'} variant="light">Ü3,5 {fmtPct(sl.p_over_35)}</Badge>
                      <Badge size="xs" color="blue" variant="outline">CS-H {fmtPct(sl.p_home_clean_sheet)}</Badge>
                      <Badge size="xs" color="teal" variant="outline">CS-A {fmtPct(sl.p_away_clean_sheet)}</Badge>
                    </Group>
                  )}
                  {(gph || gpa) && (
                    <Grid gutter="xs">
                      {gph && (
                        <GridCol span={6}>
                          <Text size="xs" fw={500} c="blue" mb={2}>{homeName}</Text>
                          <Text size="xs">≥1: {fmtPct(gph.p_ge_1_goal)} · ≥2: {fmtPct(gph.p_ge_2_goals)} · ≥3: {fmtPct(gph.p_ge_3_goals)}</Text>
                          <Text size="xs" c="dimmed">λ {fmtV(gph.lambda_weighted)}</Text>
                        </GridCol>
                      )}
                      {gpa && (
                        <GridCol span={6}>
                          <Text size="xs" fw={500} c="teal" mb={2}>{awayName}</Text>
                          <Text size="xs">≥1: {fmtPct(gpa.p_ge_1_goal)} · ≥2: {fmtPct(gpa.p_ge_2_goals)} · ≥3: {fmtPct(gpa.p_ge_3_goals)}</Text>
                          <Text size="xs" c="dimmed">λ {fmtV(gpa.lambda_weighted)}</Text>
                        </GridCol>
                      )}
                    </Grid>
                  )}
                </Stack>
            }
          </Card>
        </GridCol>
      </Grid>

      {/* Tor-Timing + Heimvorteil inline */}
      {(gth || gta || hah || haa) && (
        <Card withBorder p="sm">
          <Grid gutter="md">
            {(gth || gta) && (
              <GridCol span={{ base: 12, md: 7 }}>
                <Text size="xs" fw={600} c="dimmed" mb={4}>Tor-Timing</Text>
                <Grid gutter="xs">
                  {gth && (
                    <GridCol span={6}>
                      <Group gap={4} mb={2}>
                        <img src={teamLogoUrl(data.fixture.home_team_id)} width={14} height={14} style={{ objectFit: 'contain' }} alt="" />
                        <Text size="xs" fw={500}>{homeName}</Text>
                        {gth.profil_typ && <Badge size="xs" color="blue" variant="light">{gth.profil_typ.replace('_', ' ')}</Badge>}
                      </Group>
                      <Group gap={4} wrap="wrap">
                        {gth.p_goal_first_30 != null && <Badge size="xs" color="orange" variant="light">0–30: {fmtPct(gth.p_goal_first_30)}</Badge>}
                        {gth.p_goal_last_15 != null && <Badge size="xs" color="violet" variant="light">75+: {fmtPct(gth.p_goal_last_15)}</Badge>}
                        {gth.ht_attack_ratio != null && <Badge size="xs" color="gray" variant="light">1.HZ {fmtPct(gth.ht_attack_ratio)}</Badge>}
                      </Group>
                    </GridCol>
                  )}
                  {gta && (
                    <GridCol span={6}>
                      <Group gap={4} mb={2}>
                        <img src={teamLogoUrl(data.fixture.away_team_id)} width={14} height={14} style={{ objectFit: 'contain' }} alt="" />
                        <Text size="xs" fw={500}>{awayName}</Text>
                        {gta.profil_typ && <Badge size="xs" color="teal" variant="light">{gta.profil_typ.replace('_', ' ')}</Badge>}
                      </Group>
                      <Group gap={4} wrap="wrap">
                        {gta.p_goal_first_30 != null && <Badge size="xs" color="orange" variant="light">0–30: {fmtPct(gta.p_goal_first_30)}</Badge>}
                        {gta.p_goal_last_15 != null && <Badge size="xs" color="violet" variant="light">75+: {fmtPct(gta.p_goal_last_15)}</Badge>}
                        {gta.ht_attack_ratio != null && <Badge size="xs" color="gray" variant="light">1.HZ {fmtPct(gta.ht_attack_ratio)}</Badge>}
                      </Group>
                    </GridCol>
                  )}
                </Grid>
              </GridCol>
            )}
            {(hah || haa) && (
              <GridCol span={{ base: 12, md: 5 }}>
                <Text size="xs" fw={600} c="dimmed" mb={4}>Heimvorteil</Text>
                <Stack gap={3}>
                  {hah && (
                    <Group gap={4}>
                      <Badge size="xs" color={hah.tier === 'fortress' ? 'green' : hah.tier === 'road_team' ? 'red' : 'gray'} variant="light">{hah.tier}</Badge>
                      <Text size="xs">{homeName.split(' ')[0]}: H {fmtV(hah.home_ppg)} / A {fmtV(hah.away_ppg)} PPG</Text>
                    </Group>
                  )}
                  {haa && (
                    <Group gap={4}>
                      <Badge size="xs" color={haa.tier === 'fortress' ? 'green' : haa.tier === 'road_team' ? 'red' : 'gray'} variant="light">{haa.tier}</Badge>
                      <Text size="xs">{awayName.split(' ')[0]}: H {fmtV(haa.home_ppg)} / A {fmtV(haa.away_ppg)} PPG</Text>
                    </Group>
                  )}
                </Stack>
              </GridCol>
            )}
          </Grid>
        </Card>
      )}

      {/* Value Bets */}
      {value_bets && value_bets.length > 0 && (
        <Card withBorder p="sm">
          <Text size="xs" fw={600} c="dimmed" mb={6}>Value Bets</Text>
          <Table fz="xs" verticalSpacing={3}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Markt / Wette</Table.Th>
                <Table.Th ta="right">Modell</Table.Th>
                <Table.Th ta="right">Quote</Table.Th>
                <Table.Th ta="right">Edge</Table.Th>
                <Table.Th>Tier</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {value_bets.map((vb, i) => (
                <Table.Tr key={i}>
                  <Table.Td><Text size="xs" fw={500}>{vb.market_name} · {vb.bet_value}</Text></Table.Td>
                  <Table.Td ta="right">{fmtPct(vb.model_prob)}</Table.Td>
                  <Table.Td ta="right">{fmtV(vb.bookmaker_odd, 2)}</Table.Td>
                  <Table.Td ta="right">
                    <Text size="xs" c={vb.edge > 0 ? 'green' : 'red'} fw={600}>
                      {vb.edge > 0 ? '+' : ''}{fmtPct(vb.edge)}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="xs" color={vb.tier === 'strong' ? 'green' : vb.tier === 'value' ? 'yellow' : 'gray'} variant="light">{vb.tier}</Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Card>
      )}

      {/* Post-match evaluation */}
      {pe && (
        <Card withBorder p="sm">
          <Group gap={6} mb={6}>
            <Text size="xs" fw={600} c="dimmed">Modell-Nachbewertung</Text>
            <Badge size="xs" color={pe.outcome_correct ? 'green' : 'red'}>{pe.outcome_correct ? '✓' : '✗'} {pe.predicted_outcome}→{pe.actual_outcome}</Badge>
            <Badge size="xs" color={pe.over_25_correct ? 'green' : 'red'} variant="light">Ü2,5 {pe.over_25_correct ? '✓' : '✗'}</Badge>
            <Badge size="xs" color={pe.btts_correct ? 'green' : 'red'} variant="light">BTTS {pe.btts_correct ? '✓' : '✗'}</Badge>
            {pe.predicted_score && (
              <Badge size="xs" color={pe.score_correct ? 'green' : 'gray'} variant="outline">{pe.predicted_score} / {pe.actual_score}</Badge>
            )}
            <Text size="xs" c="dimmed">Brier: {fmtV(pe.brier_score, 3)}</Text>
          </Group>
        </Card>
      )}
    </Stack>
  )
}

// ─── Tab: Verletzungen ────────────────────────────────────────────────────────

function VerletzungenTab({ data, homeName, awayName }: {
  data: FixtureDetails; homeName: string; awayName: string
}) {
  const { injuries, injury_impacts, team_injury_impact_home: impH, team_injury_impact_away: impA, fixture } = data
  const homeInj = injuries.filter(i => i.team_id === fixture.home_team_id)
  const awayInj = injuries.filter(i => i.team_id === fixture.away_team_id)
  const byId = new Map(injury_impacts.filter(i => i.player_id != null).map(i => [i.player_id!, i]))

  const InjList = ({ list, teamId }: { list: typeof injuries; teamId: number }) => {
    if (!list.length) return <Text size="xs" c="dimmed">Keine Ausfälle.</Text>
    return (
      <Stack gap={4}>
        {list.map((inj, i) => {
          const imp = inj.player_id != null ? byId.get(inj.player_id) : undefined
          return (
            <Card key={`${inj.player_id ?? teamId}-${i}`} withBorder p="xs" radius="sm">
              <Group gap={8} wrap="nowrap" align="flex-start">
                <Avatar src={inj.player_id ? playerImageUrl(inj.player_id) : undefined} size={28} radius="xl" />
                <Stack gap={1} style={{ flex: 1 }}>
                  <Text size="xs" fw={600}>{inj.player_name ?? 'Unbekannt'}</Text>
                  {(inj.injury_type || inj.injury_reason) && (
                    <Text size="xs" c="dimmed">{inj.injury_type ?? ''}{inj.injury_reason ? ` · ${inj.injury_reason}` : ''}</Text>
                  )}
                  {imp && (
                    <Group gap={4} wrap="wrap">
                      <Badge size="xs" color={impactColor(imp.impact_bucket)} variant="light">
                        {imp.impact_bucket} {fmtV(imp.impact_score, 2)}
                      </Badge>
                      <Text size="xs" c="dimmed">W:{fmtV(imp.importance_score, 2)} B:{fmtV(imp.contribution_score, 2)} E:{fmtV(imp.replaceability_score, 2)}</Text>
                    </Group>
                  )}
                </Stack>
              </Group>
            </Card>
          )
        })}
      </Stack>
    )
  }

  return (
    <Grid gutter="md">
      <GridCol span={{ base: 12, md: 6 }}>
        <Group gap={6} mb="xs">
          <img src={teamLogoUrl(fixture.home_team_id)} width={18} height={18} style={{ objectFit: 'contain' }} alt="" />
          <Text fw={600} size="sm">{homeName}</Text>
          {impH > 0 && <Badge size="xs" color={impH > 1.5 ? 'red' : impH > .8 ? 'orange' : 'yellow'} variant="light">Impact {fmtV(impH, 2)}</Badge>}
        </Group>
        <InjList list={homeInj} teamId={fixture.home_team_id} />
      </GridCol>
      <GridCol span={{ base: 12, md: 6 }}>
        <Group gap={6} mb="xs">
          <img src={teamLogoUrl(fixture.away_team_id)} width={18} height={18} style={{ objectFit: 'contain' }} alt="" />
          <Text fw={600} size="sm">{awayName}</Text>
          {impA > 0 && <Badge size="xs" color={impA > 1.5 ? 'red' : impA > .8 ? 'orange' : 'yellow'} variant="light">Impact {fmtV(impA, 2)}</Badge>}
        </Group>
        <InjList list={awayInj} teamId={fixture.away_team_id} />
      </GridCol>
    </Grid>
  )
}

// ─── Tab: Spieldaten ─────────────────────────────────────────────────────────

function SpieldatenTab({ data, homeName, awayName }: {
  data: FixtureDetails; homeName: string; awayName: string
}) {
  const { statistics, events, fixture } = data
  const hStat = statistics.find(s => s.team_id === fixture.home_team_id)
  const aStat = statistics.find(s => s.team_id === fixture.away_team_id)
  const radarData = buildMatchRadar(hStat, aStat)

  const statRows: Array<{ label: string; key: keyof FixtureStatistic }> = [
    { label: 'Erwartete Tore (xG)', key: 'expected_goals' },
    { label: 'Ballbesitz %',        key: 'ball_possession' },
    { label: 'Schüsse gesamt',      key: 'shots_total' },
    { label: 'Schüsse aufs Tor',    key: 'shots_on_goal' },
    { label: 'Schüsse Strafraum',   key: 'shots_inside_box' },
    { label: 'Ecken',               key: 'corner_kicks' },
    { label: 'Fouls',               key: 'fouls' },
    { label: 'Abseits',             key: 'offsides' },
    { label: 'Pässe gesamt',        key: 'passes_total' },
    { label: 'Passquote %',         key: 'pass_accuracy' },
    { label: 'GK-Paraden',          key: 'goalkeeper_saves' },
    { label: 'Gelbe Karten',        key: 'yellow_cards' },
    { label: 'Rote Karten',         key: 'red_cards' },
  ]

  return (
    <Stack gap="sm">
      {/* Radar + Stats */}
      {statistics.length > 0 ? (
        <Grid gutter="md" align="flex-start">
          <GridCol span={{ base: 12, md: 6 }}>
            {radarData
              ? <RadarChart h={210} data={radarData} dataKey="axis" withLegend={false} series={RADAR_SERIES} />
              : <Center h={210}><Text size="xs" c="dimmed">Keine Statistiken</Text></Center>
            }
          </GridCol>
          <GridCol span={{ base: 12, md: 6 }}>
            <Group justify="space-between" mb={4}>
              <Text size="xs" fw={700} c="blue">{homeName}</Text>
              <Text size="xs" fw={700} c="teal">{awayName}</Text>
            </Group>
            <Stack gap={1}>
              {statRows.map(r => (
                <CRow key={r.key} label={r.label} home={statV(hStat, r.key)} away={statV(aStat, r.key)} />
              ))}
            </Stack>
          </GridCol>
        </Grid>
      ) : (
        <Alert icon={<IconInfoCircle size={14} />} color="gray" p="xs">Keine Statistikdaten.</Alert>
      )}

      {/* Events */}
      {events.length > 0 && (
        <>
          <Divider label="Match-Events" labelPosition="center" />
          <Table verticalSpacing={3} fz="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={52}>Min.</Table.Th>
                <Table.Th w={90}>Team</Table.Th>
                <Table.Th>Event</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {events.map((ev, i) => (
                <Table.Tr key={`${ev.id}-${i}`}>
                  <Table.Td c="dimmed">{fmtMinute(ev.elapsed, ev.elapsed_extra)}</Table.Td>
                  <Table.Td c="dimmed">{ev.team_name ?? ev.team_id}</Table.Td>
                  <Table.Td>
                    <Text size="xs" fw={600}>{txDetail(ev.detail) ?? txType(ev.event_type) ?? '–'}</Text>
                    <Text size="xs" c="dimmed">
                      {ev.player_name ?? '–'}{ev.assist_name ? ` · ${ev.assist_name}` : ''}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </>
      )}
    </Stack>
  )
}

// ─── Tab: KI Analyse ─────────────────────────────────────────────────────────

const CONFIDENCE_COLOR: Record<string, string> = {
  hoch: 'green',
  mittel: 'yellow',
  niedrig: 'orange',
}

function KiAnalyseTab({ fixtureId }: { fixtureId: number }) {
  // Load cached analysis on mount
  const { data: cached, isLoading: cacheLoading } = useQuery({
    queryKey: ['gpt-analysis', fixtureId],
    queryFn: () => fixturesApi.gptAnalysis(fixtureId, false),
    retry: false,
    staleTime: Infinity,
  })

  const mutation = useMutation({
    mutationFn: (force: boolean) => fixturesApi.gptAnalysis(fixtureId, force),
  })

  const data = mutation.data ?? cached
  const isLoading = cacheLoading || mutation.isPending

  return (
    <Stack gap="md">
      {isLoading && (
        <Center py="xl">
          <Stack align="center" gap="sm">
            <Loader color="violet" />
            <Text size="sm" c="dimmed">
              {mutation.isPending ? 'GPT-4o analysiert das Spiel…' : 'Lade gespeicherte Analyse…'}
            </Text>
          </Stack>
        </Center>
      )}

      {!isLoading && !data && !mutation.isError && (
        <Card withBorder p="lg">
          <Stack align="center" gap="sm">
            <IconBrain size={40} color="var(--mantine-color-violet-5)" />
            <Text fw={600} size="lg">GPT-4o Spielanalyse</Text>
            <Text size="sm" c="dimmed" ta="center" maw={480}>
              Startet eine externe KI-Analyse auf Basis aller verfügbaren Spieldaten:
              Elo, Form, Torwahrscheinlichkeit, Verletzungen, H2H und Marktwahrscheinlichkeiten.
            </Text>
            <Button
              leftSection={<IconBrain size={16} />}
              variant="filled"
              color="violet"
              mt="xs"
              onClick={() => mutation.mutate(false)}
            >
              Analyse starten
            </Button>
          </Stack>
        </Card>
      )}

      {mutation.isError && (
        <Alert color="red" title="Fehler">
          {(mutation.error as Error)?.message ?? 'Die Analyse konnte nicht geladen werden.'}
        </Alert>
      )}

      {!isLoading && data && (
        <Stack gap="md">
          {/* Analysis text */}
          <Card withBorder p="md">
            <Stack gap="xs">
              <Group justify="space-between" wrap="nowrap">
                <Group gap="xs">
                  <IconBrain size={18} color="var(--mantine-color-violet-5)" />
                  <Text fw={700} size="sm">Analyse</Text>
                  <Badge size="xs" color="violet" variant="light">{data.model}</Badge>
                  {data.cached && <Badge size="xs" color="gray" variant="outline">gespeichert</Badge>}
                </Group>
                {data.generated_at && (
                  <Text size="xs" c="dimmed">
                    {dayjs(data.generated_at).format('DD.MM.YYYY HH:mm')} Uhr
                  </Text>
                )}
              </Group>
              <Text size="sm" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
                {data.analysis}
              </Text>
            </Stack>
          </Card>

          {/* Betting tips */}
          <Text fw={700} size="sm">5 Wetttipps</Text>
          <Stack gap="sm">
            {(data.betting_tips ?? []).map((tip: {
              tip_nr: number
              market: string
              pick: string
              confidence: string
              reasoning: string
            }) => (
              <Paper key={tip.tip_nr} withBorder p="sm" radius="md">
                <Group justify="space-between" wrap="nowrap" align="flex-start">
                  <Stack gap={4} style={{ flex: 1 }}>
                    <Group gap="xs" wrap="nowrap">
                      <Badge size="sm" variant="outline" color="violet">#{tip.tip_nr}</Badge>
                      <Text size="sm" fw={600}>{tip.market}</Text>
                      <Text size="sm" fw={700} c="blue">→ {tip.pick}</Text>
                    </Group>
                    <Text size="xs" c="dimmed">{tip.reasoning}</Text>
                  </Stack>
                  <Badge
                    size="sm"
                    color={CONFIDENCE_COLOR[tip.confidence] ?? 'gray'}
                    variant="filled"
                    style={{ flexShrink: 0 }}
                  >
                    {tip.confidence}
                  </Badge>
                </Group>
              </Paper>
            ))}
          </Stack>

          <Button
            variant="subtle"
            size="xs"
            color="violet"
            leftSection={<IconBrain size={14} />}
            loading={mutation.isPending}
            onClick={() => mutation.mutate(true)}
          >
            Neu generieren
          </Button>
        </Stack>
      )}
    </Stack>
  )
}


// ─── Main page ────────────────────────────────────────────────────────────────

export function MatchDetailsPage() {
  const { fixtureId } = useParams<{ fixtureId: string }>()
  const navigate = useNavigate()
  const id = Number(fixtureId)

  const { data, isLoading, error } = useQuery({
    queryKey: ['fixture-details', id],
    queryFn: () => fixturesApi.details(id),
    enabled: Number.isFinite(id) && id > 0,
  })
  const fix = data?.fixture

  const { data: hs } = useQuery({
    queryKey: ['team-summary', fix?.home_team_id, fix?.season_year, fix?.league_id],
    queryFn: () => teamsApi.summary(fix!.home_team_id, fix!.season_year, fix!.league_id),
    enabled: !!fix,
  })
  const { data: as_ } = useQuery({
    queryKey: ['team-summary', fix?.away_team_id, fix?.season_year, fix?.league_id],
    queryFn: () => teamsApi.summary(fix!.away_team_id, fix!.season_year, fix!.league_id),
    enabled: !!fix,
  })
  const { data: homeElo } = useQuery({
    queryKey: ['team-elo', fix?.home_team_id, fix?.season_year, fix?.league_id],
    queryFn: () => teamsApi.elo(fix!.home_team_id, fix!.season_year, fix!.league_id),
    enabled: !!fix,
  })
  const { data: awayElo } = useQuery({
    queryKey: ['team-elo', fix?.away_team_id, fix?.season_year, fix?.league_id],
    queryFn: () => teamsApi.elo(fix!.away_team_id, fix!.season_year, fix!.league_id),
    enabled: !!fix,
  })
  const { data: leagueEloRows = [] } = useQuery({
    queryKey: ['league-elo', fix?.league_id, fix?.season_year],
    queryFn: () => leaguesApi.elo(fix!.league_id, fix!.season_year),
    enabled: !!fix,
  })
  const { data: homeForm } = useQuery({
    queryKey: ['team-form', fix?.home_team_id, fix?.season_year, fix?.league_id, 5],
    queryFn: () => teamsApi.form(fix!.home_team_id, fix!.season_year, fix!.league_id, 5),
    enabled: !!fix,
  })
  const { data: awayForm } = useQuery({
    queryKey: ['team-form', fix?.away_team_id, fix?.season_year, fix?.league_id, 5],
    queryFn: () => teamsApi.form(fix!.away_team_id, fix!.season_year, fix!.league_id, 5),
    enabled: !!fix,
  })

  if (isLoading) return <Center py="xl"><Loader /></Center>
  if (error || !data) return <Alert color="red" title="Fehler">Match-Details konnten nicht geladen werden.</Alert>

  const { fixture } = data
  const home = fixture.home_team_name ?? `Team ${fixture.home_team_id}`
  const away = fixture.away_team_name ?? `Team ${fixture.away_team_id}`
  const homeScopeForm = homeForm?.scopes.find(s => s.scope === 'home') ?? null
  const awayScopeForm = awayForm?.scopes.find(s => s.scope === 'away') ?? null
  const eloByTeam = Object.fromEntries(leagueEloRows.map(r => [r.team_id, r.elo_overall])) as Record<number, number>
  const rankByTeam = Object.fromEntries(leagueEloRows.map(r => [r.team_id, r.rank])) as Record<number, number>
  const isFinished = ['FT', 'AET', 'PEN'].includes(fixture.status_short ?? '')
  const hasMatchData = data.statistics.length > 0 || data.events.length > 0

  return (
    <Stack gap="sm">
      {/* Header */}
      <Group justify="space-between" align="flex-start">
        <Stack gap={2}>
          <Group gap="xs" style={{ cursor: 'pointer' }} onClick={() => navigate(`/liga/${fixture.league_id}`)}>
            <IconArrowLeft size={14} />
            <Text size="xs" c="dimmed">Zur Liga</Text>
          </Group>
          <Group gap="xs">
            <img src={leagueLogoUrl(fixture.league_id)} width={20} height={20} alt="" />
            <Title order={3}>{fixture.league_name}</Title>
            <Badge size="xs" variant="light">Spieltag {fixture.matchday ?? '–'}</Badge>
          </Group>
          <Text size="xs" c="dimmed">
            {fixture.kickoff_utc ? dayjs(fixture.kickoff_utc + 'Z').format('DD.MM.YYYY HH:mm') : '–'}
            {fixture.venue_name ? ` · ${fixture.venue_name}` : ''}
          </Text>
        </Stack>
        <Badge color="blue" variant="dot" size="sm">{STATUS_LABELS[fixture.status_short ?? ''] ?? fixture.status_short ?? '–'}</Badge>
      </Group>

      {/* Team card */}
      <Card withBorder p="sm">
        <Group justify="space-between" align="center" wrap="nowrap" gap="xs">
          <Stack gap={3} align="center" style={{ flex: 1 }}>
            <FormLogo teamId={fixture.home_team_id} teamName={home}
              score={homeScopeForm?.form_score ?? null} trend={homeScopeForm?.form_trend ?? null} />
            <Text fw={700} ta="center" size="sm" style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/team/${fixture.home_team_id}?season_year=${fixture.season_year}&league_id=${fixture.league_id}`)}>
              {home}
            </Text>
            <Group gap={4} justify="center" wrap="nowrap">
              <Badge size="xs" variant="light" color="indigo">Elo {homeElo?.elo_overall.toFixed(0) ?? '–'}</Badge>
              {homeElo?.strength_tier && <Badge size="xs" color="gray" variant="outline">{homeElo.strength_tier}</Badge>}
            </Group>
            <FormPills matches={hs?.last_matches} ownElo={homeElo?.elo_overall} eloByTeam={eloByTeam} rankByTeam={rankByTeam} />
          </Stack>

          <Stack align="center" gap={2} px="xs">
            <Text fw={900} fz={28} lh={1}>{fixture.home_score ?? '–'} : {fixture.away_score ?? '–'}</Text>
            {fixture.home_ht_score != null && (
              <Text size="xs" c="dimmed">HZ {fixture.home_ht_score}:{fixture.away_ht_score}</Text>
            )}
          </Stack>

          <Stack gap={3} align="center" style={{ flex: 1 }}>
            <FormLogo teamId={fixture.away_team_id} teamName={away}
              score={awayScopeForm?.form_score ?? null} trend={awayScopeForm?.form_trend ?? null} />
            <Text fw={700} ta="center" size="sm" style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/team/${fixture.away_team_id}?season_year=${fixture.season_year}&league_id=${fixture.league_id}`)}>
              {away}
            </Text>
            <Group gap={4} justify="center" wrap="nowrap">
              <Badge size="xs" variant="light" color="indigo">Elo {awayElo?.elo_overall.toFixed(0) ?? '–'}</Badge>
              {awayElo?.strength_tier && <Badge size="xs" color="gray" variant="outline">{awayElo.strength_tier}</Badge>}
            </Group>
            <FormPills matches={as_?.last_matches} ownElo={awayElo?.elo_overall} eloByTeam={eloByTeam} rankByTeam={rankByTeam} />
          </Stack>
        </Group>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="vergleich" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="vergleich">Vergleich</Tabs.Tab>
          <Tabs.Tab value="prognose">Prognose</Tabs.Tab>
          <Tabs.Tab value="verletzungen">
            Verletzungen
            {data.injuries.length > 0 && (
              <Badge size="xs" color="red" variant="filled" ml={4}>{data.injuries.length}</Badge>
            )}
          </Tabs.Tab>
          {(isFinished || hasMatchData) && <Tabs.Tab value="spieldaten">Spieldaten</Tabs.Tab>}
          <Tabs.Tab value="ki-analyse" leftSection={<IconBrain size={14} />}>KI Analyse</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="vergleich" pt="sm">
          <TeamVergleichTab homeId={fixture.home_team_id} awayId={fixture.away_team_id}
            hs={hs} as_={as_} h2h={data.h2h ?? null} homeName={home} awayName={away} />
        </Tabs.Panel>

        <Tabs.Panel value="prognose" pt="sm">
          <PrognoseTab data={data} homeName={home} awayName={away} />
        </Tabs.Panel>

        <Tabs.Panel value="verletzungen" pt="sm">
          <VerletzungenTab data={data} homeName={home} awayName={away} />
        </Tabs.Panel>

        {(isFinished || hasMatchData) && (
          <Tabs.Panel value="spieldaten" pt="sm">
            <SpieldatenTab data={data} homeName={home} awayName={away} />
          </Tabs.Panel>
        )}

        <Tabs.Panel value="ki-analyse" pt="sm">
          <KiAnalyseTab fixtureId={fixture.id} />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  )
}

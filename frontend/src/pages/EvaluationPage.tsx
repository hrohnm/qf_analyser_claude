import {
  Badge,
  Card,
  Center,
  Grid,
  GridCol,
  Group,
  Loader,
  RingProgress,
  Select,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fixturesApi, type EvaluationRow } from '../api'
import { teamLogoUrl } from '../types'

// ── Helpers ───────────────────────────────────────────────────────────────────

function pct(v: number | null) {
  if (v == null) return '–'
  return `${(v * 100).toFixed(1)}%`
}
function fmtDate(s: string | null) {
  if (!s) return '–'
  return dayjs(s + 'Z').format('DD.MM. HH:mm')
}

const DATE_OPTIONS = [
  { value: '1',  label: 'Gestern' },
  { value: '3',  label: 'Letzte 3 Tage' },
  { value: '7',  label: 'Letzte 7 Tage' },
  { value: '14', label: 'Letzte 14 Tage' },
  { value: '30', label: 'Letzte 30 Tage' },
]

function emitted1x2(row: EvaluationRow) {
  const probs = [
    { pick: 'H', prob: row.p_home_win },
    { pick: 'D', prob: row.p_draw },
    { pick: 'A', prob: row.p_away_win },
  ].sort((a, b) => b.prob - a.prob)
  const margin = probs[0].prob - probs[1].prob
  const confidence = Math.max(0, Math.min(1, 0.65 * probs[0].prob + 0.35 * Math.min(1, margin / 0.20)))
  return confidence >= 0.58 && margin >= 0.06
}

function emittedDc(row: EvaluationRow) {
  const options = [
    row.p_home_win + row.p_draw,
    row.p_draw + row.p_away_win,
    row.p_home_win + row.p_away_win,
  ].sort((a, b) => b - a)
  return options[0] >= 0.68 && (options[0] - options[1]) >= 0.04
}

function emittedBinary(prob: number | null, minConfidence: number) {
  if (prob == null) return false
  return Math.max(prob, 1 - prob) >= minConfidence
}

// ── Summary stats card ────────────────────────────────────────────────────────

function SummaryCard({ rows }: { rows: EvaluationRow[] }) {
  if (!rows.length) return null
  const n = rows.length

  const cnt = (pred: (r: EvaluationRow) => boolean | null) => {
    const valid = rows.filter(r => pred(r) != null)
    return { hits: valid.filter(r => pred(r) === true).length, total: valid.length }
  }

  const c1x2  = cnt(r => r.outcome_correct)
  const cDC   = cnt(r => r.dc_correct ?? null)
  const cOU25 = cnt(r => r.over_25_correct)
  const cOU15 = cnt(r => r.over_15_correct ?? null)
  const cBTTS = cnt(r => r.btts_correct)
  const cHScr = cnt(r => r.home_scores_correct ?? null)
  const cAScr = cnt(r => r.away_scores_correct ?? null)
  const cScore = cnt(r => r.score_correct)
  const avgBrier     = rows.reduce((s, r) => s + r.brier_score, 0) / n
  const avgGoalsDiff = rows.reduce((s, r) => s + r.goals_diff, 0) / n

  const Ring = ({ label, hits, total, tooltip }: { label: string; hits: number; total: number; tooltip?: string }) => {
    if (!total) return null
    const rate = hits / total
    const color = rate >= 0.6 ? 'green' : rate >= 0.45 ? 'yellow' : 'red'
    return (
      <Stack align="center" gap={2}>
        <RingProgress size={72} thickness={5} roundCaps sections={[{ value: rate * 100, color }]}
          label={<Text size="xs" fw={700} ta="center">{(rate * 100).toFixed(0)}%</Text>}
        />
        <Tooltip label={tooltip ?? label} withArrow fz="xs" disabled={!tooltip}>
          <Text size="xs" c="dimmed" ta="center">{label}</Text>
        </Tooltip>
        <Text size="10px" c="dimmed">{hits}/{total}</Text>
      </Stack>
    )
  }

  return (
    <Card withBorder radius="md" p="md">
      <Group justify="space-between" mb="sm" wrap="wrap" gap="xs">
        <Title order={5}>Gesamtübersicht</Title>
        <Badge variant="light" color="gray">{n} Spiele</Badge>
      </Group>
      <Group justify="space-around" wrap="wrap" gap="md">
        <Ring label="1X2"     {...c1x2}  tooltip="Richtiger Ausgang (Heim/Unentsch./Auswärts)" />
        <Ring label="DC"      {...cDC}   tooltip="Doppelte Chance korrekt" />
        <Ring label="O2.5"    {...cOU25} tooltip="Over/Under 2.5 korrekt" />
        <Ring label="O1.5"    {...cOU15} tooltip="Over/Under 1.5 korrekt" />
        <Ring label="BTTS"    {...cBTTS} tooltip="Both Teams To Score korrekt" />
        <Ring label="H⚽"      {...cHScr} tooltip="Heimteam trifft korrekt" />
        <Ring label="A⚽"      {...cAScr} tooltip="Auswärtsteam trifft korrekt" />
        <Ring label="Ergebnis" {...cScore} tooltip="Exaktes Ergebnis getroffen" />
        <Stack align="center" gap={2}>
          <Text size="xl" fw={800} c={avgBrier < 0.5 ? 'green' : avgBrier < 0.7 ? 'yellow' : 'red'}>
            {avgBrier.toFixed(3)}
          </Text>
          <Text size="xs" c="dimmed">Ø Brier</Text>
          <Text size="10px" c="dimmed">(0=perfekt)</Text>
        </Stack>
        <Stack align="center" gap={2}>
          <Text size="xl" fw={800} c={avgGoalsDiff < 1 ? 'green' : avgGoalsDiff < 1.5 ? 'yellow' : 'red'}>
            Δ{avgGoalsDiff.toFixed(2)}
          </Text>
          <Text size="xs" c="dimmed">Ø Tore Δ</Text>
          <Text size="10px" c="dimmed">(λ vs. tatsächlich)</Text>
        </Stack>
      </Group>
    </Card>
  )
}

function CoverageCard({ rows }: { rows: EvaluationRow[] }) {
  if (!rows.length) return null

  const items = [
    {
      label: '1X2',
      covered: rows.filter(emitted1x2),
      correct: (r: EvaluationRow) => r.outcome_correct,
      color: 'blue',
    },
    {
      label: 'DC',
      covered: rows.filter(emittedDc),
      correct: (r: EvaluationRow) => r.dc_correct === true,
      color: 'indigo',
    },
    {
      label: 'O1.5',
      covered: rows.filter(r => emittedBinary(r.p_over_15, 0.67)),
      correct: (r: EvaluationRow) => r.over_15_correct === true,
      color: 'cyan',
    },
    {
      label: 'O2.5',
      covered: rows.filter(r => emittedBinary(r.p_over_25, 0.62)),
      correct: (r: EvaluationRow) => r.over_25_correct,
      color: 'violet',
    },
    {
      label: 'BTTS',
      covered: rows.filter(r => emittedBinary(r.p_btts, 0.62)),
      correct: (r: EvaluationRow) => r.btts_correct,
      color: 'teal',
    },
    {
      label: 'H⚽',
      covered: rows.filter(r => emittedBinary(r.p_home_scores, 0.64)),
      correct: (r: EvaluationRow) => r.home_scores_correct === true,
      color: 'orange',
    },
    {
      label: 'A⚽',
      covered: rows.filter(r => emittedBinary(r.p_away_scores, 0.64)),
      correct: (r: EvaluationRow) => r.away_scores_correct === true,
      color: 'grape',
    },
  ]

  return (
    <Card withBorder radius="md" p="md">
      <Title order={5} mb="sm">Coverage vs Accuracy</Title>
      <Grid gutter="xs">
        {items.map(item => {
          const coverage = item.covered.length
          const coveragePct = rows.length ? (coverage / rows.length) * 100 : 0
          const accuracy = coverage ? (item.covered.filter(item.correct).length / coverage) * 100 : 0
          return (
            <GridCol key={item.label} span={{ base: 6, sm: 4, md: 3 }}>
              <Card withBorder p="xs" radius="sm">
                <Group justify="space-between" mb={4}>
                  <Text size="xs" fw={700}>{item.label}</Text>
                  <Badge size="xs" color={item.color} variant="light">{coveragePct.toFixed(0)}% Cov</Badge>
                </Group>
                <Text size="lg" fw={800} c={accuracy >= 60 ? 'green' : accuracy >= 52 ? 'yellow' : 'red'}>
                  {coverage ? `${accuracy.toFixed(0)}%` : '–'}
                </Text>
                <Text size="xs" c="dimmed">Accuracy auf emitted Picks</Text>
                <Text size="10px" c="dimmed" mt={4}>{coverage}/{rows.length} Spiele</Text>
              </Card>
            </GridCol>
          )
        })}
      </Grid>
    </Card>
  )
}

// ── Outcome badge ─────────────────────────────────────────────────────────────

function OutcomeBadge({ correct, predicted, actual }: { correct: boolean; predicted: string; actual: string }) {
  const lbl = (o: string) => o === 'H' ? 'H' : o === 'D' ? 'X' : 'A'
  return (
    <Badge size="xs" color={correct ? 'green' : 'red'} variant="light">
      {lbl(predicted)}→{lbl(actual)}
    </Badge>
  )
}

function YesNo({ correct }: { correct: boolean | null }) {
  if (correct == null) return <Text size="xs" c="dimmed">–</Text>
  return <Text size="xs" fw={700} c={correct ? 'green' : 'red'}>{correct ? '✓' : '✗'}</Text>
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function EvaluationPage() {
  const navigate = useNavigate()
  const [days, setDays] = useState('7')

  const fromDate = dayjs().subtract(Number(days), 'day').format('YYYY-MM-DD')
  const toDate   = dayjs().format('YYYY-MM-DD')

  const { data = [], isLoading } = useQuery({
    queryKey: ['evaluations', fromDate, toDate],
    queryFn: () => fixturesApi.evaluations({ from_date: fromDate, to_date: toDate, season_year: 2025 }),
  })

  return (
    <Stack gap="md" p="md">
      <Group justify="space-between" wrap="wrap" gap="xs">
        <Title order={3}>Pattern-Auswertung</Title>
        <Select size="xs" data={DATE_OPTIONS} value={days} onChange={v => v && setDays(v)} w={160} />
      </Group>

      {isLoading ? (
        <Center py="xl"><Loader /></Center>
      ) : data.length === 0 ? (
        <Text c="dimmed">Keine Auswertungen für den gewählten Zeitraum.</Text>
      ) : (
        <>
          <SummaryCard rows={data} />
          <CoverageCard rows={data} />
          <LeagueBreakdown rows={data} />

          <Card withBorder radius="md" p={0} style={{ overflow: 'auto' }}>
            <Table striped highlightOnHover withTableBorder={false} verticalSpacing="xs" fz="xs" style={{ minWidth: 1100 }}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Datum</Table.Th>
                  <Table.Th>Liga</Table.Th>
                  <Table.Th ta="right">Heim</Table.Th>
                  <Table.Th ta="center">Erg.</Table.Th>
                  <Table.Th>Gast</Table.Th>
                  <Table.Th ta="center">1X2</Table.Th>
                  <Table.Th ta="center">DC</Table.Th>
                  <Table.Th ta="center">Wkt.</Table.Th>
                  <Table.Th ta="center">Tipp</Table.Th>
                  <Table.Th ta="center">O2.5</Table.Th>
                  <Table.Th ta="center">O1.5</Table.Th>
                  <Table.Th ta="center">BTTS</Table.Th>
                  <Table.Th ta="center">H⚽</Table.Th>
                  <Table.Th ta="center">A⚽</Table.Th>
                  <Table.Th ta="center">Tore Δ</Table.Th>
                  <Table.Th ta="center">Brier</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.map(row => (
                  <Table.Tr key={row.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/spiel/${row.id}`)}>
                    <Table.Td><Text size="xs" c="dimmed">{fmtDate(row.kickoff_utc)}</Text></Table.Td>
                    <Table.Td><Text size="xs" c="dimmed">{row.league_name}</Text></Table.Td>
                    <Table.Td ta="right">
                      <Group gap={4} justify="flex-end" wrap="nowrap">
                        <Text size="xs" fw={500}>{row.home_team_name}</Text>
                        {row.home_team_id && <img src={teamLogoUrl(row.home_team_id)} width={14} height={14} alt="" style={{ objectFit: 'contain' }} />}
                      </Group>
                    </Table.Td>
                    <Table.Td ta="center">
                      <Text size="xs" fw={700}>{row.home_score}:{row.away_score}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap={4} wrap="nowrap">
                        {row.away_team_id && <img src={teamLogoUrl(row.away_team_id)} width={14} height={14} alt="" style={{ objectFit: 'contain' }} />}
                        <Text size="xs" fw={500}>{row.away_team_name}</Text>
                      </Group>
                    </Table.Td>
                    <Table.Td ta="center">
                      <OutcomeBadge correct={row.outcome_correct} predicted={row.predicted_outcome} actual={row.actual_outcome} />
                    </Table.Td>
                    <Table.Td ta="center">
                      {row.dc_correct != null && row.dc_prediction ? (
                        <Tooltip label={`${row.dc_prediction} · ${pct(row.dc_prob)}`} withArrow fz="xs">
                          <Badge size="xs" color={row.dc_correct ? 'green' : 'red'} variant="light">{row.dc_prediction}</Badge>
                        </Tooltip>
                      ) : <Text size="xs" c="dimmed">–</Text>}
                    </Table.Td>
                    <Table.Td ta="center">
                      <Tooltip label={`1:${pct(row.p_home_win)} X:${pct(row.p_draw)} 2:${pct(row.p_away_win)}`} withArrow fz="xs">
                        <Text size="xs">{pct(row.p_actual_outcome)}</Text>
                      </Tooltip>
                    </Table.Td>
                    <Table.Td ta="center">
                      <Tooltip label={`Tipp: ${row.predicted_score ?? '–'}`} withArrow fz="xs">
                        <Badge size="xs" color={row.score_correct ? 'green' : 'gray'} variant="light">
                          {row.predicted_score ?? '–'}→{row.actual_score}
                        </Badge>
                      </Tooltip>
                    </Table.Td>
                    <Table.Td ta="center">
                      <Tooltip label={`${pct(row.p_over_25)} · ${row.actual_total_goals} Tore`} withArrow fz="xs">
                        <span><YesNo correct={row.over_25_correct} /></span>
                      </Tooltip>
                    </Table.Td>
                    <Table.Td ta="center">
                      <Tooltip label={pct(row.p_over_15)} withArrow fz="xs">
                        <span><YesNo correct={row.over_15_correct ?? null} /></span>
                      </Tooltip>
                    </Table.Td>
                    <Table.Td ta="center">
                      <Tooltip label={pct(row.p_btts)} withArrow fz="xs">
                        <span><YesNo correct={row.btts_correct} /></span>
                      </Tooltip>
                    </Table.Td>
                    <Table.Td ta="center">
                      <Tooltip label={pct(row.p_home_scores)} withArrow fz="xs">
                        <span><YesNo correct={row.home_scores_correct ?? null} /></span>
                      </Tooltip>
                    </Table.Td>
                    <Table.Td ta="center">
                      <Tooltip label={pct(row.p_away_scores)} withArrow fz="xs">
                        <span><YesNo correct={row.away_scores_correct ?? null} /></span>
                      </Tooltip>
                    </Table.Td>
                    <Table.Td ta="center">
                      <Text size="xs" c={row.goals_diff < 1 ? 'green' : row.goals_diff < 2 ? 'yellow' : 'red'}>
                        {row.predicted_total_goals.toFixed(1)} ({row.actual_total_goals})
                      </Text>
                    </Table.Td>
                    <Table.Td ta="center">
                      <Text size="xs" fw={600} c={row.brier_score < 0.5 ? 'green' : row.brier_score < 0.8 ? 'yellow' : 'red'}>
                        {row.brier_score.toFixed(3)}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>
        </>
      )}
    </Stack>
  )
}

// ── League breakdown ──────────────────────────────────────────────────────────

function LeagueBreakdown({ rows }: { rows: EvaluationRow[] }) {
  const byLeague = new Map<string, EvaluationRow[]>()
  for (const r of rows) {
    const key = r.league_name ?? 'Unbekannt'
    if (!byLeague.has(key)) byLeague.set(key, [])
    byLeague.get(key)!.push(r)
  }

  const leagues = [...byLeague.entries()]
    .filter(([, rs]) => rs.length >= 3)
    .sort((a, b) => b[1].length - a[1].length)

  if (!leagues.length) return null

  const rate = (rs: EvaluationRow[], pred: (r: EvaluationRow) => boolean | null) => {
    const valid = rs.filter(r => pred(r) != null)
    if (!valid.length) return null
    return (valid.filter(r => pred(r) === true).length / valid.length * 100).toFixed(0)
  }

  return (
    <Card withBorder radius="md" p="md">
      <Title order={5} mb="sm">Nach Liga</Title>
      <Grid gutter="xs">
        {leagues.map(([name, rs]) => {
          const n = rs.length
          const br = (rs.reduce((s, r) => s + r.brier_score, 0) / n).toFixed(3)
          const r1x2 = rate(rs, r => r.outcome_correct)
          const rDC  = rate(rs, r => r.dc_correct ?? null)
          const rOU25 = rate(rs, r => r.over_25_correct)
          const rOU15 = rate(rs, r => r.over_15_correct ?? null)
          const rBTTS = rate(rs, r => r.btts_correct)
          const rHScr = rate(rs, r => r.home_scores_correct ?? null)
          const rAScr = rate(rs, r => r.away_scores_correct ?? null)
          return (
            <GridCol key={name} span={{ base: 6, sm: 4, md: 3 }}>
              <Card withBorder p="xs" radius="sm">
                <Text size="xs" fw={600} mb={4} lineClamp={1}>{name}</Text>
                <Group gap={3} wrap="wrap">
                  {r1x2  && <Badge size="xs" color="blue"   variant="light">1X2 {r1x2}%</Badge>}
                  {rDC   && <Badge size="xs" color="indigo" variant="light">DC {rDC}%</Badge>}
                  {rOU25 && <Badge size="xs" color="violet" variant="light">O2.5 {rOU25}%</Badge>}
                  {rOU15 && <Badge size="xs" color="cyan"   variant="light">O1.5 {rOU15}%</Badge>}
                  {rBTTS && <Badge size="xs" color="teal"   variant="light">BTTS {rBTTS}%</Badge>}
                  {rHScr && <Badge size="xs" color="orange" variant="light">H⚽ {rHScr}%</Badge>}
                  {rAScr && <Badge size="xs" color="grape"  variant="light">A⚽ {rAScr}%</Badge>}
                  <Badge size="xs" color="gray" variant="outline">B {br}</Badge>
                </Group>
                <Text size="10px" c="dimmed" mt={4}>{n} Spiele</Text>
              </Card>
            </GridCol>
          )
        })}
      </Grid>
    </Card>
  )
}

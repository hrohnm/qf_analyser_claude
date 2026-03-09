import {
  Alert,
  Badge,
  Card,
  Center,
  Grid,
  GridCol,
  Group,
  Loader,
  Paper,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { IconArrowLeft } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { teamsApi } from '../api'
import { teamLogoUrl } from '../types'

const RESULT_COLOR: Record<string, string> = {
  W: 'green',
  D: 'yellow',
  L: 'red',
}

function MetricCard({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <Paper withBorder p="sm" radius="md">
      <Text size="xs" c="dimmed">{label}</Text>
      <Text fw={700} size="lg">{value}</Text>
      {hint ? <Text size="xs" c="dimmed">{hint}</Text> : null}
    </Paper>
  )
}

function perGame(total: number, played: number) {
  if (!played) return '–'
  return (total / played).toFixed(1).replace('.', ',')
}

function fmtPct(value: number | null | undefined) {
  return value == null ? '–' : `${value.toFixed(1).replace('.', ',')}%`
}

export function TeamPage() {
  const navigate = useNavigate()
  const { teamId } = useParams<{ teamId: string }>()
  const [search] = useSearchParams()

  const id = Number(teamId)
  const seasonYear = Number(search.get('season_year') ?? '2025')
  const leagueIdParam = search.get('league_id')
  const leagueId = leagueIdParam ? Number(leagueIdParam) : undefined

  const { data, isLoading, error } = useQuery({
    queryKey: ['team-summary', id, seasonYear, leagueId],
    queryFn: () => teamsApi.summary(id, seasonYear, leagueId),
    enabled: Number.isFinite(id) && id > 0,
  })

  if (isLoading) return <Center py="xl"><Loader /></Center>
  if (error || !data) return <Alert color="red" title="Fehler">Teamdaten konnten nicht geladen werden.</Alert>

  return (
    <Stack gap="md">
      <Group gap="xs" style={{ cursor: 'pointer' }} onClick={() => navigate(-1)}>
        <IconArrowLeft size={16} />
        <Text size="sm" c="dimmed">Zurück</Text>
      </Group>

      <Card withBorder>
        <Group justify="space-between" align="center">
          <Group>
            <img src={data.team_logo_url ?? teamLogoUrl(data.team_id)} width={38} height={38} alt={data.team_name} />
            <Stack gap={0}>
              <Title order={2}>{data.team_name}</Title>
              <Text size="sm" c="dimmed">
                Saison {data.season_year}/{data.season_year + 1}
                {data.league_id != null ? ` · Liga-ID ${data.league_id}` : ''}
              </Text>
            </Stack>
          </Group>
          <Group gap={8}>
            {data.form.split('').map((c, i) => (
              <Badge key={`${c}-${i}`} color={RESULT_COLOR[c] ?? 'gray'}>{c}</Badge>
            ))}
          </Group>
        </Group>
      </Card>

      <SimpleGrid cols={{ base: 2, sm: 3, md: 6 }}>
        <MetricCard label="Punkte" value={data.points} hint={`${data.played} Spiele`} />
        <MetricCard label="Bilanz" value={`${data.won}-${data.drawn}-${data.lost}`} hint="S-U-N" />
        <MetricCard label="Tore" value={`${data.goals_for}:${data.goals_against}`} hint={`Diff ${data.goal_diff >= 0 ? '+' : ''}${data.goal_diff}`} />
        <MetricCard label="Ø Tore" value={`${data.avg_goals_for} / ${data.avg_goals_against}`} hint="pro Spiel" />
        <MetricCard label="Heim / Auswärts" value={`${data.home_points} / ${data.away_points}`} hint="Punkte" />
        <MetricCard label="xG gesamt" value={data.xg_total ?? '–'} />
      </SimpleGrid>

      <Grid gutter="md">
        <GridCol span={{ base: 12, md: 6 }}>
          <Card withBorder>
            <Title order={4} mb="sm">Aggregierte Team-Statistiken</Title>
            <Table verticalSpacing="xs" fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Wert</Table.Th>
                  <Table.Th ta="right">Gesamt</Table.Th>
                  <Table.Th ta="right">Pro Spiel</Table.Th>
                  <Table.Th ta="right">Heim/Spiel</Table.Th>
                  <Table.Th ta="right">Auswärts/Spiel</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                <Table.Tr>
                  <Table.Td>Ø Ballbesitz</Table.Td>
                  <Table.Td ta="right">{fmtPct(data.avg_ball_possession)}</Table.Td>
                  <Table.Td ta="right">{fmtPct(data.avg_ball_possession)}</Table.Td>
                  <Table.Td ta="right">{fmtPct(data.avg_ball_possession_home)}</Table.Td>
                  <Table.Td ta="right">{fmtPct(data.avg_ball_possession_away)}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Schüsse gesamt</Table.Td>
                  <Table.Td ta="right">{data.shots_total}</Table.Td>
                  <Table.Td ta="right">{perGame(data.shots_total, data.played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.shots_total_home, data.home_played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.shots_total_away, data.away_played)}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Schüsse aufs Tor</Table.Td>
                  <Table.Td ta="right">{data.shots_on_goal}</Table.Td>
                  <Table.Td ta="right">{perGame(data.shots_on_goal, data.played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.shots_on_goal_home, data.home_played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.shots_on_goal_away, data.away_played)}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Ecken</Table.Td>
                  <Table.Td ta="right">{data.corners}</Table.Td>
                  <Table.Td ta="right">{perGame(data.corners, data.played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.corners_home, data.home_played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.corners_away, data.away_played)}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Fouls</Table.Td>
                  <Table.Td ta="right">{data.fouls}</Table.Td>
                  <Table.Td ta="right">{perGame(data.fouls, data.played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.fouls_home, data.home_played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.fouls_away, data.away_played)}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Gelbe Karten</Table.Td>
                  <Table.Td ta="right">{data.yellow_cards}</Table.Td>
                  <Table.Td ta="right">{perGame(data.yellow_cards, data.played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.yellow_cards_home, data.home_played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.yellow_cards_away, data.away_played)}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Rote Karten</Table.Td>
                  <Table.Td ta="right">{data.red_cards}</Table.Td>
                  <Table.Td ta="right">{perGame(data.red_cards, data.played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.red_cards_home, data.home_played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.red_cards_away, data.away_played)}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Pässe gesamt</Table.Td>
                  <Table.Td ta="right">{data.passes_total}</Table.Td>
                  <Table.Td ta="right">{perGame(data.passes_total, data.played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.passes_total_home, data.home_played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.passes_total_away, data.away_played)}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Pässe angekommen</Table.Td>
                  <Table.Td ta="right">{data.passes_accurate}</Table.Td>
                  <Table.Td ta="right">{perGame(data.passes_accurate, data.played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.passes_accurate_home, data.home_played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.passes_accurate_away, data.away_played)}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Passquote</Table.Td>
                  <Table.Td ta="right">{data.pass_accuracy_pct != null ? `${data.pass_accuracy_pct}%` : '–'}</Table.Td>
                  <Table.Td ta="right">{data.pass_accuracy_pct != null ? `${data.pass_accuracy_pct.toFixed(1).replace('.', ',')}%` : '–'}</Table.Td>
                  <Table.Td ta="right">{data.passes_total_home ? `${((data.passes_accurate_home / data.passes_total_home) * 100).toFixed(1).replace('.', ',')}%` : '–'}</Table.Td>
                  <Table.Td ta="right">{data.passes_total_away ? `${((data.passes_accurate_away / data.passes_total_away) * 100).toFixed(1).replace('.', ',')}%` : '–'}</Table.Td>
                </Table.Tr>
              </Table.Tbody>
            </Table>
          </Card>
        </GridCol>

        <GridCol span={{ base: 12, md: 6 }}>
          <Card withBorder>
            <Title order={4} mb="sm">Events (aggregiert)</Title>
            <Table verticalSpacing="xs" fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Event</Table.Th>
                  <Table.Th ta="right">Gesamt</Table.Th>
                  <Table.Th ta="right">Pro Spiel</Table.Th>
                  <Table.Th ta="right">Heim/Spiel</Table.Th>
                  <Table.Th ta="right">Auswärts/Spiel</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                <Table.Tr>
                  <Table.Td>Tore</Table.Td>
                  <Table.Td ta="right">{data.events_goals}</Table.Td>
                  <Table.Td ta="right">{perGame(data.events_goals, data.played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.events_goals_home, data.home_played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.events_goals_away, data.away_played)}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Gelbe Karten</Table.Td>
                  <Table.Td ta="right">{data.events_yellow_cards}</Table.Td>
                  <Table.Td ta="right">{perGame(data.events_yellow_cards, data.played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.events_yellow_cards_home, data.home_played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.events_yellow_cards_away, data.away_played)}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Rote Karten</Table.Td>
                  <Table.Td ta="right">{data.events_red_cards}</Table.Td>
                  <Table.Td ta="right">{perGame(data.events_red_cards, data.played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.events_red_cards_home, data.home_played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.events_red_cards_away, data.away_played)}</Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Wechsel</Table.Td>
                  <Table.Td ta="right">{data.events_substitutions}</Table.Td>
                  <Table.Td ta="right">{perGame(data.events_substitutions, data.played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.events_substitutions_home, data.home_played)}</Table.Td>
                  <Table.Td ta="right">{perGame(data.events_substitutions_away, data.away_played)}</Table.Td>
                </Table.Tr>
              </Table.Tbody>
            </Table>
          </Card>
        </GridCol>
      </Grid>

      <Card withBorder>
        <Title order={4} mb="sm">Letzte Spiele</Title>
        <Table verticalSpacing="xs" fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Datum</Table.Th>
              <Table.Th>Gegner</Table.Th>
              <Table.Th ta="center">Ort</Table.Th>
              <Table.Th ta="center">Ergebnis</Table.Th>
              <Table.Th ta="center">Form</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.last_matches.map(m => (
              <Table.Tr
                key={m.fixture_id}
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/spiel/${m.fixture_id}`)}
              >
                <Table.Td>{m.kickoff_utc ? dayjs(m.kickoff_utc + 'Z').format('DD.MM. HH:mm') : '–'}</Table.Td>
                <Table.Td>{m.opponent_team_name}</Table.Td>
                <Table.Td ta="center">{m.is_home ? 'H' : 'A'}</Table.Td>
                <Table.Td ta="center">{m.goals_for ?? '–'}:{m.goals_against ?? '–'}</Table.Td>
                <Table.Td ta="center">
                  <Badge color={RESULT_COLOR[m.result ?? ''] ?? 'gray'} size="sm">{m.result ?? '–'}</Badge>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>
    </Stack>
  )
}

import {
  Badge, Group, Image, Progress, ScrollArea, Select, Stack, Table, Text, Tooltip,
} from '@mantine/core'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { leaguesApi, type TeamProfileRow } from '../../api'
import { useQuery } from '@tanstack/react-query'
import { teamLogoUrl } from '../../types'

// ── Sort options ───────────────────────────────────────────────────────────────

const SORT_OPTIONS = [
  { value: 'attack_rating',    label: 'Angriff-Rating' },
  { value: 'defense_rating',   label: 'Abwehr-Rating' },
  { value: 'intensity_rating', label: 'Intensität-Rating' },
  { value: 'goals_scored_pg',  label: 'Tore/Spiel' },
  { value: 'goals_conceded_pg', label: 'Gegentore/Spiel' },
  { value: 'xg_over_performance', label: 'xG-Überperformance' },
]

// ── Rating badge ───────────────────────────────────────────────────────────────

function RatingBar({ value, invert = false }: { value: number | null; invert?: boolean }) {
  if (value == null) return <Text size="xs" c="dimmed">–</Text>
  const color = invert
    ? (value >= 60 ? 'red' : value >= 40 ? 'yellow' : 'green')
    : (value >= 60 ? 'green' : value >= 40 ? 'yellow' : 'red')
  return (
    <Group gap={6} wrap="nowrap">
      <Progress value={value} color={color} size="sm" w={60} />
      <Text size="xs" fw={600} c={color}>{value.toFixed(0)}</Text>
    </Group>
  )
}

function Num({ v, decimals = 2, suffix = '' }: { v: number | null; decimals?: number; suffix?: string }) {
  if (v == null) return <Text size="xs" c="dimmed">–</Text>
  return <Text size="xs">{v.toFixed(decimals)}{suffix}</Text>
}

function PerfBadge({ v }: { v: number | null }) {
  if (v == null) return <Text size="xs" c="dimmed">–</Text>
  const color = v > 0.2 ? 'green' : v < -0.2 ? 'red' : 'gray'
  const label = v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2)
  return <Badge size="xs" color={color} variant="light">{label}</Badge>
}

// ── Tab views ─────────────────────────────────────────────────────────────────

type TabKey = 'ratings' | 'attack' | 'defense' | 'style'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'ratings',  label: 'Ratings' },
  { key: 'attack',   label: 'Angriff' },
  { key: 'defense',  label: 'Abwehr' },
  { key: 'style',    label: 'Spielstil' },
]

// ── Main component ─────────────────────────────────────────────────────────────

export function TeamProfilesTable({
  leagueId,
  seasonYear,
  onTeamClick,
}: {
  leagueId: number
  seasonYear: number
  onTeamClick?: (teamId: number) => void
}) {
  const [sortBy, setSortBy] = useState('attack_rating')
  const [tab, setTab] = useState<TabKey>('ratings')

  const { data: rows = [], isLoading } = useQuery({
    queryKey: ['team-profiles', leagueId, seasonYear, sortBy],
    queryFn: () => leaguesApi.teamProfiles(leagueId, seasonYear, sortBy),
    enabled: !!leagueId,
  })

  if (isLoading) return <Text size="xs" c="dimmed">Lade Teamprofile…</Text>
  if (!rows.length) return <Text size="xs" c="dimmed">Keine Teamprofile verfügbar.</Text>

  return (
    <Stack gap="xs">
      {/* Controls */}
      <Group justify="space-between" wrap="wrap" gap="xs">
        <Group gap={6}>
          {TABS.map(t => (
            <Badge
              key={t.key}
              variant={tab === t.key ? 'filled' : 'light'}
              color="blue"
              style={{ cursor: 'pointer' }}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </Badge>
          ))}
        </Group>
        <Select
          size="xs"
          w={180}
          data={SORT_OPTIONS}
          value={sortBy}
          onChange={v => v && setSortBy(v)}
          label={undefined}
        />
      </Group>

      <ScrollArea>
        <Table
          striped
          highlightOnHover
          withTableBorder={false}
          verticalSpacing="xs"
          fz="xs"
          style={{ minWidth: tab === 'style' ? 720 : 680 }}
        >
          <Table.Thead>
            <Table.Tr>
              <Table.Th style={{ width: 28 }}>#</Table.Th>
              <Table.Th>Team</Table.Th>
              <Table.Th ta="center" style={{ width: 36 }}>Sp.</Table.Th>
              {tab === 'ratings' && <>
                <Table.Th>Angriff</Table.Th>
                <Table.Th>Abwehr</Table.Th>
                <Table.Th>Intensität</Table.Th>
                <Table.Th ta="center">
                  <Tooltip label="Tore über/unter xG-Erwartung" withArrow fz="xs">
                    <span>xG Off</span>
                  </Tooltip>
                </Table.Th>
                <Table.Th ta="center">
                  <Tooltip label="Gegentore unter/über xG against — positiv = besser als xG" withArrow fz="xs">
                    <span>xG Def</span>
                  </Tooltip>
                </Table.Th>
              </>}
              {tab === 'attack' && <>
                <Table.Th ta="right">Tore/Sp</Table.Th>
                <Table.Th ta="right">xG/Sp</Table.Th>
                <Table.Th ta="right">Schüsse/Sp</Table.Th>
                <Table.Th ta="right">SaT/Sp</Table.Th>
                <Table.Th ta="right">
                  <Tooltip label="Schüsse auf Tor / Schüsse gesamt" withArrow fz="xs"><span>SaT%</span></Tooltip>
                </Table.Th>
                <Table.Th ta="right">
                  <Tooltip label="Tore / Schüsse auf Tor" withArrow fz="xs"><span>Konv%</span></Tooltip>
                </Table.Th>
                <Table.Th ta="right">Box/Sp</Table.Th>
              </>}
              {tab === 'defense' && <>
                <Table.Th ta="right">GT/Sp</Table.Th>
                <Table.Th ta="right">xGA/Sp</Table.Th>
                <Table.Th ta="right">CS%</Table.Th>
                <Table.Th ta="right">Sch.g/Sp</Table.Th>
                <Table.Th ta="right">SaT g/Sp</Table.Th>
                <Table.Th ta="right">Saves/Sp</Table.Th>
              </>}
              {tab === 'style' && <>
                <Table.Th ta="right">Bstz%</Table.Th>
                <Table.Th ta="right">Pässe/Sp</Table.Th>
                <Table.Th ta="right">Pass%</Table.Th>
                <Table.Th ta="right">Ecken/Sp</Table.Th>
                <Table.Th ta="right">Fouls/Sp</Table.Th>
                <Table.Th ta="right">Gelb/Sp</Table.Th>
                <Table.Th ta="right">Abs/Sp</Table.Th>
              </>}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((row, i) => (
              <Table.Tr
                key={row.team_id}
                style={{ cursor: onTeamClick ? 'pointer' : undefined }}
                onClick={() => onTeamClick?.(row.team_id)}
              >
                <Table.Td>
                  <Text size="xs" c="dimmed">{i + 1}</Text>
                </Table.Td>
                <Table.Td>
                  <Group gap={6} wrap="nowrap">
                    <img src={teamLogoUrl(row.team_id)} width={16} height={16} style={{ objectFit: 'contain' }} alt="" />
                    <Text size="xs" fw={500}>{row.team_name}</Text>
                  </Group>
                </Table.Td>
                <Table.Td ta="center">
                  <Text size="xs" c="dimmed">{row.games_played}</Text>
                </Table.Td>

                {tab === 'ratings' && <>
                  <Table.Td><RatingBar value={row.attack_rating} /></Table.Td>
                  <Table.Td><RatingBar value={row.defense_rating} /></Table.Td>
                  <Table.Td><RatingBar value={row.intensity_rating} /></Table.Td>
                  <Table.Td ta="center"><PerfBadge v={row.xg_over_performance} /></Table.Td>
                  <Table.Td ta="center"><PerfBadge v={row.xg_defense_performance} /></Table.Td>
                </>}

                {tab === 'attack' && <>
                  <Table.Td ta="right"><Num v={row.goals_scored_pg} /></Table.Td>
                  <Table.Td ta="right"><Num v={row.xg_for_pg} /></Table.Td>
                  <Table.Td ta="right"><Num v={row.shots_total_pg} decimals={1} /></Table.Td>
                  <Table.Td ta="right"><Num v={row.shots_on_target_pg} decimals={1} /></Table.Td>
                  <Table.Td ta="right"><Num v={row.shots_on_target_ratio != null ? row.shots_on_target_ratio * 100 : null} decimals={1} suffix="%" /></Table.Td>
                  <Table.Td ta="right"><Num v={row.shot_conversion_rate != null ? row.shot_conversion_rate * 100 : null} decimals={1} suffix="%" /></Table.Td>
                  <Table.Td ta="right"><Num v={row.shots_inside_box_pg} decimals={1} /></Table.Td>
                </>}

                {tab === 'defense' && <>
                  <Table.Td ta="right"><Num v={row.goals_conceded_pg} /></Table.Td>
                  <Table.Td ta="right"><Num v={row.xg_against_pg} /></Table.Td>
                  <Table.Td ta="right"><Num v={row.clean_sheet_rate != null ? row.clean_sheet_rate * 100 : null} decimals={1} suffix="%" /></Table.Td>
                  <Table.Td ta="right"><Num v={row.shots_against_pg} decimals={1} /></Table.Td>
                  <Table.Td ta="right"><Num v={row.shots_on_target_against_pg} decimals={1} /></Table.Td>
                  <Table.Td ta="right"><Num v={row.gk_saves_pg} decimals={1} /></Table.Td>
                </>}

                {tab === 'style' && <>
                  <Table.Td ta="right"><Num v={row.possession_avg} decimals={1} suffix="%" /></Table.Td>
                  <Table.Td ta="right"><Num v={row.passes_pg} decimals={0} /></Table.Td>
                  <Table.Td ta="right"><Num v={row.pass_accuracy_avg} decimals={1} suffix="%" /></Table.Td>
                  <Table.Td ta="right"><Num v={row.corners_pg} decimals={1} /></Table.Td>
                  <Table.Td ta="right"><Num v={row.fouls_pg} decimals={1} /></Table.Td>
                  <Table.Td ta="right"><Num v={row.yellow_cards_pg} decimals={2} /></Table.Td>
                  <Table.Td ta="right"><Num v={row.offsides_pg} decimals={1} /></Table.Td>
                </>}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea>
    </Stack>
  )
}

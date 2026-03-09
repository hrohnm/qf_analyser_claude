import {
  Avatar,
  Badge,
  Card,
  Center,
  Group,
  Loader,
  NumberInput,
  Select,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { leaguesApi, playersApi } from '../api'

function fmtDate(value: string | null) {
  if (!value) return '–'
  return dayjs(value + 'Z').format('DD.MM.YYYY')
}

export function PlayersPage() {
  const navigate = useNavigate()
  const currentSeason = new Date().getMonth() >= 6 ? new Date().getFullYear() : new Date().getFullYear() - 1

  const [seasonYear, setSeasonYear] = useState<number>(currentSeason)
  const [leagueId, setLeagueId] = useState<number | undefined>(undefined)
  const [limit, setLimit] = useState<number>(300)

  const { data: leagues = [] } = useQuery({
    queryKey: ['leagues'],
    queryFn: leaguesApi.list,
    staleTime: Infinity,
  })

  const { data: players = [], isLoading } = useQuery({
    queryKey: ['players-overview', seasonYear, leagueId, limit],
    queryFn: () => playersApi.overview({
      season_year: seasonYear,
      league_id: leagueId,
      limit,
      offset: 0,
    }),
  })

  const leagueOptions = useMemo(
    () => leagues.map(l => ({ value: String(l.id), label: `${l.country} · ${l.name}` })),
    [leagues],
  )

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-end">
        <Stack gap={2}>
          <Title order={2}>Spielerübersicht</Title>
          <Text c="dimmed" size="sm">Aggregiert aus Match-Events (Tore, Vorlagen, Karten, Wechsel)</Text>
        </Stack>

        <Group align="flex-end">
          <Select
            label="Liga"
            placeholder="Alle"
            clearable
            searchable
            value={leagueId != null ? String(leagueId) : null}
            onChange={(v) => setLeagueId(v ? Number(v) : undefined)}
            data={leagueOptions}
            w={260}
          />
          <Select
            label="Saison"
            value={String(seasonYear)}
            onChange={(v) => v && setSeasonYear(Number(v))}
            data={['2022', '2023', '2024', '2025'].map(y => ({ value: y, label: `${y}/${Number(y) + 1}` }))}
            w={120}
          />
          <NumberInput
            label="Zeilen"
            value={limit}
            onChange={(v) => setLimit(Number(v) || 300)}
            min={50}
            max={1000}
            step={50}
            w={110}
          />
        </Group>
      </Group>

      <Card withBorder>
        {isLoading ? (
          <Center py="xl"><Loader /></Center>
        ) : (
          <Table verticalSpacing="xs" fz="sm" striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Spieler</Table.Th>
                <Table.Th>Team</Table.Th>
                <Table.Th ta="right">Spiele</Table.Th>
                <Table.Th ta="right">Tore</Table.Th>
                <Table.Th ta="right">Vorlagen</Table.Th>
                <Table.Th ta="right">Gelb</Table.Th>
                <Table.Th ta="right">Rot</Table.Th>
                <Table.Th ta="right">Wechsel</Table.Th>
                <Table.Th ta="right">Events</Table.Th>
                <Table.Th>Letztes Event</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {players.map((p) => (
                <Table.Tr key={`${p.player_id ?? 'name'}-${p.player_name}`}>
                  <Table.Td>
                    <Text fw={600}>{p.player_name}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Group gap={6}>
                      {p.team_id ? (
                        <Avatar src={p.team_logo_url} size={18} radius="sm" />
                      ) : null}
                      <Text
                        size="sm"
                        style={{ cursor: p.team_id ? 'pointer' : 'default' }}
                        onClick={() => {
                          if (!p.team_id) return
                          navigate(`/team/${p.team_id}?season_year=${seasonYear}${leagueId ? `&league_id=${leagueId}` : ''}`)
                        }}
                      >
                        {p.team_name ?? '–'}
                      </Text>
                    </Group>
                  </Table.Td>
                  <Table.Td ta="right">{p.matches}</Table.Td>
                  <Table.Td ta="right"><Badge color="green" variant="light">{p.goals}</Badge></Table.Td>
                  <Table.Td ta="right">{p.assists}</Table.Td>
                  <Table.Td ta="right">{p.yellow_cards}</Table.Td>
                  <Table.Td ta="right">{p.red_cards}</Table.Td>
                  <Table.Td ta="right">{p.substitutions}</Table.Td>
                  <Table.Td ta="right">{p.events_total}</Table.Td>
                  <Table.Td>{fmtDate(p.last_event_utc)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>
    </Stack>
  )
}

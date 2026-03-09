import {
  Stack, Title, Group, Text, Badge, Loader, Center,
  Paper, Image, ActionIcon, Tooltip, Divider
} from '@mantine/core'
import { IconChevronLeft, IconChevronRight, IconCalendar, IconRefresh } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import 'dayjs/locale/de'
import { fixturesApi } from '../api'
import { MatchCard } from '../components/common/MatchCard'
import { leagueLogoUrl, countryFlagUrl, COUNTRY_FLAGS, type Fixture } from '../types'

dayjs.locale('de')

const COUNTRY_ORDER = ['Germany', 'England', 'Spain', 'France', 'Italy', 'Turkey']
const COUNTRY_NAMES: Record<string, string> = {
  Germany: 'Deutschland', England: 'England', Spain: 'Spanien',
  France: 'Frankreich', Italy: 'Italien', Turkey: 'Türkei',
}

function toDateStr(d: dayjs.Dayjs) {
  return d.format('YYYY-MM-DD')
}

function groupByCountryAndLeague(fixtures: Fixture[]) {
  const result: Record<string, Record<number, { leagueName: string; leagueTier: number; fixtures: Fixture[] }>> = {}
  for (const f of fixtures) {
    const country = f.league_country ?? 'Sonstige'
    const lid = f.league_id
    if (!result[country]) result[country] = {}
    if (!result[country][lid]) result[country][lid] = {
      leagueName: f.league_name ?? String(lid),
      leagueTier: f.league_tier ?? 99,
      fixtures: [],
    }
    result[country][lid].fixtures.push(f)
  }
  return result
}

export function TodayPage() {
  const navigate = useNavigate()
  const [offset, setOffset] = useState(0) // days from today
  const activeDate = dayjs().add(offset, 'day')
  const dateStr = toDateStr(activeDate)

  const { data: fixtures = [], isLoading, refetch } = useQuery({
    queryKey: ['fixtures-today', dateStr],
    queryFn: () => fixturesApi.today(dateStr),
    staleTime: 1000 * 60 * 5,
  })

  const grouped = groupByCountryAndLeague(fixtures)
  const finishedCount = fixtures.filter(f => ['FT', 'AET', 'PEN'].includes(f.status_short ?? '')).length
  const liveCount = fixtures.filter(f => ['1H', 'HT', '2H'].includes(f.status_short ?? '')).length
  const nsCount = fixtures.filter(f => f.status_short === 'NS').length

  const isToday = offset === 0
  const dateLabel = isToday
    ? 'Heute'
    : offset === 1
    ? 'Morgen'
    : offset === -1
    ? 'Gestern'
    : activeDate.format('dddd, DD. MMMM')

  return (
    <Stack gap="md">
      {/* Header */}
      <Group justify="space-between" align="center">
        <Stack gap={2}>
          <Title order={2}>Spieltag</Title>
          <Text c="dimmed" size="sm">Spiele unserer 18 Ligen</Text>
        </Stack>

        {/* Datums-Navigation */}
        <Group gap="xs">
          <ActionIcon variant="subtle" onClick={() => setOffset(o => o - 1)}>
            <IconChevronLeft size={18} />
          </ActionIcon>

          <Group gap={6} style={{ minWidth: 180, justifyContent: 'center' }}>
            <IconCalendar size={16} />
            <Text fw={600} size="sm">{dateLabel}</Text>
            <Text c="dimmed" size="xs">{activeDate.format('DD.MM.YYYY')}</Text>
          </Group>

          <ActionIcon variant="subtle" onClick={() => setOffset(o => o + 1)}>
            <IconChevronRight size={18} />
          </ActionIcon>

          {isToday && (
            <Tooltip label="Aktualisieren">
              <ActionIcon variant="subtle" onClick={() => refetch()}>
                <IconRefresh size={16} />
              </ActionIcon>
            </Tooltip>
          )}
        </Group>

        {/* Statistik-Badges */}
        <Group gap={6}>
          {liveCount > 0 && <Badge color="yellow" variant="filled" size="sm">{liveCount} Live</Badge>}
          {finishedCount > 0 && <Badge color="green" variant="light" size="sm">{finishedCount} beendet</Badge>}
          {nsCount > 0 && <Badge color="gray" variant="light" size="sm">{nsCount} ausstehend</Badge>}
          {fixtures.length === 0 && !isLoading && <Badge color="gray" variant="light" size="sm">0 Spiele</Badge>}
        </Group>
      </Group>

      {/* Inhalt */}
      {isLoading ? (
        <Center py="xl"><Loader /></Center>
      ) : fixtures.length === 0 ? (
        <Paper withBorder p="xl" radius="md">
          <Stack align="center" gap="xs">
            <Text size="xl">📅</Text>
            <Text fw={500}>Keine Spiele am {activeDate.format('DD.MM.YYYY')}</Text>
            <Text c="dimmed" size="sm">In unseren 18 Ligen finden an diesem Tag keine Partien statt.</Text>
          </Stack>
        </Paper>
      ) : (
        <Stack gap="md">
          {COUNTRY_ORDER.filter(c => grouped[c]).map(country => {
            const leaguesInCountry = Object.entries(grouped[country])
              .sort(([, a], [, b]) => a.leagueTier - b.leagueTier)

            return (
              <Stack key={country} gap="sm">
                {/* Land-Header */}
                <Group gap={8}>
                  <Image
                    src={countryFlagUrl(country)}
                    w={22} h={16} fit="contain"
                    fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
                  />
                  <Text fw={700} size="sm" tt="uppercase" c="dimmed" style={{ letterSpacing: '0.05em' }}>
                    {COUNTRY_FLAGS[country]} {COUNTRY_NAMES[country]}
                  </Text>
                </Group>

                {leaguesInCountry.map(([leagueIdStr, leagueData]) => {
                  const leagueId = Number(leagueIdStr)
                  return (
                    <Paper key={leagueId} withBorder radius="md" style={{ overflow: 'hidden' }}>
                      {/* Liga-Header */}
                      <Group
                        px="md" py="xs"
                        gap="sm"
                        style={{ cursor: 'pointer', borderBottom: '1px solid var(--mantine-color-default-border)' }}
                        onClick={() => navigate(`/liga/${leagueId}`)}
                      >
                        <Image
                          src={leagueLogoUrl(leagueId)}
                          w={24} h={24} fit="contain"
                          fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
                        />
                        <Text fw={600} size="sm">{leagueData.leagueName}</Text>
                        <Badge size="xs" variant="outline" color="green" ml="auto">
                          {leagueData.fixtures.length} Spiele
                        </Badge>
                      </Group>

                      {/* Spiele */}
                      <Stack gap={0} px="sm" py="xs">
                        {leagueData.fixtures.map((f, i) => (
                          <div key={f.id}>
                            {i > 0 && <Divider my={4} />}
                            <MatchCard fixture={f} onClick={() => navigate(`/spiel/${f.id}`)} />
                          </div>
                        ))}
                      </Stack>
                    </Paper>
                  )
                })}
              </Stack>
            )
          })}
        </Stack>
      )}
    </Stack>
  )
}

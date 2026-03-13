import {
  Stack, Group, ActionIcon, Text, Loader, Center, Divider, Badge
} from '@mantine/core'
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import 'dayjs/locale/de'
import { fixturesApi } from '../../api'
import { MatchCard } from '../common/MatchCard'

dayjs.locale('de')

interface Props {
  leagueId: number
  seasonYear: number
  eloByTeam?: Record<number, number>
  matchday: number
  maxMatchday: number
  onMatchdayChange: (md: number) => void
}

export function MatchdayView({ leagueId, seasonYear, eloByTeam, matchday, maxMatchday, onMatchdayChange }: Props) {
  const navigate = useNavigate()
  const { data: fixtures = [], isLoading } = useQuery({
    queryKey: ['fixtures-matchday', leagueId, seasonYear, matchday],
    queryFn: () => fixturesApi.list({
      league_id: leagueId,
      season_year: seasonYear,
      matchday,
      limit: 30,
    }),
    enabled: matchday > 0,
  })

  const byDate = fixtures.reduce<Record<string, typeof fixtures>>((acc, f) => {
    const dateKey = f.kickoff_utc
      ? dayjs(f.kickoff_utc + 'Z').format('dddd, DD. MMMM YYYY')
      : 'Datum unbekannt'
    ;(acc[dateKey] ??= []).push(f)
    return acc
  }, {})

  const finishedCount = fixtures.filter(f =>
    ['FT', 'AET', 'PEN'].includes(f.status_short ?? '')
  ).length

  return (
    <Stack gap="sm">
      {/* Pfeil-Navigation */}
      <Group justify="space-between" align="center">
        <ActionIcon
          variant="subtle"
          disabled={matchday <= 1}
          onClick={() => onMatchdayChange(matchday - 1)}
          size="md"
        >
          <IconChevronLeft size={18} />
        </ActionIcon>

        <Group gap={6}>
          <Badge size="sm" variant="light" color="green">{finishedCount} ✓</Badge>
          <Badge size="sm" variant="light" color="gray">
            {fixtures.length - finishedCount} ausstehend
          </Badge>
        </Group>

        <ActionIcon
          variant="subtle"
          disabled={matchday >= maxMatchday}
          onClick={() => onMatchdayChange(matchday + 1)}
          size="md"
        >
          <IconChevronRight size={18} />
        </ActionIcon>
      </Group>

      {/* Spiele */}
      {isLoading ? (
        <Center py="md"><Loader size="sm" /></Center>
      ) : fixtures.length === 0 ? (
        <Text c="dimmed" ta="center" size="sm">Keine Spiele für Spieltag {matchday}.</Text>
      ) : (
        <Stack gap={4}>
          {Object.entries(byDate).map(([date, dayFixtures]) => (
            <Stack key={date} gap={4}>
              <Divider
                label={<Text size="xs" c="dimmed">{date}</Text>}
                labelPosition="left"
              />
              {dayFixtures.map(f => (
                <MatchCard
                  key={f.id}
                  fixture={f}
                  eloByTeam={eloByTeam}
                  onClick={() => navigate(`/spiel/${f.id}`)}
                />
              ))}
            </Stack>
          ))}
        </Stack>
      )}
    </Stack>
  )
}

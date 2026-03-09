import { SimpleGrid, Card, Text, Group, Badge, Stack, Title, Anchor } from '@mantine/core'
import { useNavigate } from 'react-router-dom'
import { useLeagues } from '../hooks/useLeagues'
import { COUNTRY_FLAGS } from '../types'

const COUNTRY_ORDER = ['Germany', 'England', 'Spain', 'France', 'Italy', 'Turkey']
const COUNTRY_NAMES: Record<string, string> = {
  Germany: 'Deutschland',
  England: 'England',
  Spain: 'Spanien',
  France: 'Frankreich',
  Italy: 'Italien',
  Turkey: 'Türkei',
}

export function DashboardPage() {
  const { data: leagues = [], isLoading } = useLeagues()
  const navigate = useNavigate()

  const grouped = COUNTRY_ORDER.reduce<Record<string, typeof leagues>>((acc, country) => {
    acc[country] = leagues.filter(l => l.country === country).sort((a, b) => a.tier - b.tier)
    return acc
  }, {})

  if (isLoading) {
    return <Text c="dimmed">Lade Ligen…</Text>
  }

  if (leagues.length === 0) {
    return (
      <Stack align="center" mt="xl">
        <Text size="lg" fw={500}>Noch keine Daten in der Datenbank.</Text>
        <Text c="dimmed">
          Gehe zu{' '}
          <Anchor onClick={() => navigate('/sync')}>Sync & Budget</Anchor>
          {' '}und starte den Fixture-Sync.
        </Text>
      </Stack>
    )
  }

  return (
    <Stack>
      <Title order={2}>Übersicht</Title>
      <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
        {COUNTRY_ORDER.map(country => {
          const countryLeagues = grouped[country] ?? []
          if (!countryLeagues.length) return null
          return (
            <Card key={country} withBorder padding="md" radius="md">
              <Group mb="sm">
                <Text size="xl">{COUNTRY_FLAGS[country]}</Text>
                <Text fw={600}>{COUNTRY_NAMES[country]}</Text>
              </Group>
              <Stack gap="xs">
                {countryLeagues.map(league => (
                  <Group
                    key={league.id}
                    justify="space-between"
                    style={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/liga/${league.id}`)}
                    p="xs"
                    styles={{
                      root: {
                        borderRadius: 6,
                        '&:hover': { backgroundColor: 'var(--mantine-color-dark-6)' },
                      }
                    }}
                  >
                    <Text size="sm">{league.name}</Text>
                    <Badge size="xs" variant="outline" color="green">
                      Liga {league.tier}
                    </Badge>
                  </Group>
                ))}
              </Stack>
            </Card>
          )
        })}
      </SimpleGrid>
    </Stack>
  )
}

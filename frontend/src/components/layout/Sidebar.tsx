import { NavLink, Stack, Text, Divider, Loader, Box } from '@mantine/core'
import { useNavigate, useLocation } from 'react-router-dom'
import { IconSettings, IconDatabase, IconCalendarEvent, IconUsers } from '@tabler/icons-react'
import { useLeagues } from '../../hooks/useLeagues'
import { useUiStore } from '../../store/uiStore'
import { COUNTRY_FLAGS } from '../../types'

const COUNTRY_ORDER = ['Germany', 'England', 'Spain', 'France', 'Italy', 'Turkey']
const COUNTRY_NAMES: Record<string, string> = {
  Germany: 'Deutschland',
  England: 'England',
  Spain: 'Spanien',
  France: 'Frankreich',
  Italy: 'Italien',
  Turkey: 'Türkei',
}

export function Sidebar() {
  const { data: leagues, isLoading } = useLeagues()
  const { selectedLeagueId, setLeague } = useUiStore()
  const navigate = useNavigate()
  const location = useLocation()

  const grouped = COUNTRY_ORDER.reduce<Record<string, typeof leagues>>((acc, country) => {
    acc[country] = (leagues ?? [])
      .filter(l => l.country === country)
      .sort((a, b) => a.tier - b.tier)
    return acc
  }, {})

  const isDataBrowser = location.pathname.startsWith('/liga')

  return (
    <Stack gap={0} p="xs" h="100%">
      {/* Startseite */}
      <NavLink
        label="Spieltag"
        leftSection={<IconCalendarEvent size={16} />}
        active={location.pathname === '/'}
        onClick={() => navigate('/')}
        mb={4}
      />

      {/* Datenbrowser */}
      <NavLink
        label="Datenbrowser"
        leftSection={<IconDatabase size={16} />}
        childrenOffset={12}
        defaultOpened={isDataBrowser}
      >
        {isLoading && <Loader size="xs" mx="auto" my="xs" />}

        {COUNTRY_ORDER.map(country => {
          const countryLeagues = grouped[country] ?? []
          if (!countryLeagues.length) return null
          return (
            <NavLink
              key={country}
              label={
                <Text size="xs" fw={600}>
                  {COUNTRY_FLAGS[country]} {COUNTRY_NAMES[country]}
                </Text>
              }
              childrenOffset={10}
              defaultOpened
            >
              {countryLeagues.map(league => (
                <NavLink
                  key={league.id}
                  label={league.name}
                  active={selectedLeagueId === league.id}
                  onClick={() => {
                    setLeague(league.id)
                    navigate(`/liga/${league.id}`)
                  }}
                  styles={{ label: { fontSize: '0.8rem' } }}
                />
              ))}
            </NavLink>
          )
        })}
      </NavLink>

      <NavLink
        label="Spieler"
        leftSection={<IconUsers size={16} />}
        active={location.pathname === '/spieler'}
        onClick={() => navigate('/spieler')}
        mt={4}
      />

      <Box mt="auto">
        <Divider mb="xs" />
        <NavLink
          label="Sync & Budget"
          leftSection={<IconSettings size={16} />}
          active={location.pathname === '/sync'}
          onClick={() => navigate('/sync')}
        />
      </Box>
    </Stack>
  )
}

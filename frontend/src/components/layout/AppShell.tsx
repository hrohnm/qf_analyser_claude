import { AppShell, Burger, Group, Title, useMantineColorScheme, ActionIcon, Tabs } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconSun, IconMoon, IconCalendarEvent, IconDatabase, IconTicket, IconUsers, IconSettings, IconShieldCog, IconChartBar } from '@tabler/icons-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { BudgetIndicator } from './BudgetIndicator'
import { useUiStore } from '../../store/uiStore'

interface Props {
  children: React.ReactNode
}

const NAV_TABS = [
  { value: 'spieltag',    label: 'Spieltag',     icon: <IconCalendarEvent size={15} />, path: '/' },
  { value: 'datenbrowser',label: 'Datenbrowser', icon: <IconDatabase size={15} />,      path: '/liga' },
  { value: 'wettscheine', label: 'Wettscheine',  icon: <IconTicket size={15} />,        path: '/wettscheine' },
  { value: 'auswertung',  label: 'Auswertung',   icon: <IconChartBar size={15} />,      path: '/auswertung' },
  { value: 'spieler',     label: 'Spieler',      icon: <IconUsers size={15} />,         path: '/spieler' },
  { value: 'sync',        label: 'Sync',         icon: <IconSettings size={15} />,      path: '/sync' },
  { value: 'admin',       label: 'Administration',icon: <IconShieldCog size={15} />,    path: '/admin' },
]

function activeTab(pathname: string): string {
  if (pathname === '/') return 'spieltag'
  if (pathname.startsWith('/liga') || pathname.startsWith('/team')) return 'datenbrowser'
  if (pathname.startsWith('/wettscheine')) return 'wettscheine'
  if (pathname.startsWith('/auswertung')) return 'auswertung'
  if (pathname.startsWith('/spieler')) return 'spieler'
  if (pathname.startsWith('/sync')) return 'sync'
  if (pathname.startsWith('/admin')) return 'admin'
  return 'spieltag'
}

// Sidebar nur auf Seiten mit Filter-/Browser-Inhalt einblenden
function showNavbar(pathname: string) {
  return pathname === '/' || pathname.startsWith('/liga') || pathname.startsWith('/team')
}

export function AppLayout({ children }: Props) {
  const [opened, { toggle }] = useDisclosure()
  const { colorScheme, toggleColorScheme } = useMantineColorScheme()
  const navigate = useNavigate()
  const location = useLocation()
  const { setActiveLeagueFilter } = useUiStore()

  const currentTab = activeTab(location.pathname)
  const sidebarVisible = showNavbar(location.pathname)

  function handleTabChange(value: string | null) {
    const tab = NAV_TABS.find(t => t.value === value)
    if (!tab) return
    if (value === 'spieltag') setActiveLeagueFilter(null)
    navigate(tab.path)
  }

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: 240,
        breakpoint: 'sm',
        collapsed: { mobile: !opened, desktop: !sidebarVisible },
      }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" gap="lg" wrap="nowrap">
          {/* Logo */}
          <Group gap="xs" wrap="nowrap" style={{ flexShrink: 0 }}>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={4} fw={700} c="green" style={{ whiteSpace: 'nowrap' }}>
              ⚽ Quotenfabrik
            </Title>
          </Group>

          {/* Tab-Navigation */}
          <Tabs
            value={currentTab}
            onChange={handleTabChange}
            style={{ flex: 1 }}
            styles={{
              root: { height: '100%' },
              list: {
                height: '100%',
                borderBottom: 'none',
                gap: 2,
                flexWrap: 'nowrap',
              },
              tab: {
                height: '100%',
                paddingTop: 0,
                paddingBottom: 0,
                borderBottom: '2px solid transparent',
                borderRadius: 0,
                fontSize: '0.85rem',
                fontWeight: 500,
              },
            }}
          >
            <Tabs.List>
              {NAV_TABS.map(tab => (
                <Tabs.Tab key={tab.value} value={tab.value} leftSection={tab.icon}>
                  {tab.label}
                </Tabs.Tab>
              ))}
            </Tabs.List>
          </Tabs>

          {/* Rechts: Budget + Theme-Toggle */}
          <Group gap="sm" wrap="nowrap" style={{ flexShrink: 0 }}>
            <BudgetIndicator />
            <ActionIcon variant="subtle" onClick={() => toggleColorScheme()} size="sm">
              {colorScheme === 'dark' ? <IconSun size={16} /> : <IconMoon size={16} />}
            </ActionIcon>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar>
        <Sidebar />
      </AppShell.Navbar>

      <AppShell.Main>
        {children}
      </AppShell.Main>
    </AppShell>
  )
}

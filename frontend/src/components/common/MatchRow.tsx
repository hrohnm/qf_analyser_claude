import { Box, Group, Text, Image, Tooltip } from '@mantine/core'
import { IconRobot } from '@tabler/icons-react'
import dayjs from 'dayjs'
import 'dayjs/locale/de'
import type { EnrichedFixture, FixtureEvaluation } from '../../api'
import type { Fixture } from '../../types'
import { teamLogoUrl } from '../../types'

dayjs.locale('de')

// ─── Grid column template ──────────────────────────────────────────────────
// time | home | score-box | away | predictions (fixed width = sync across all rows)
export const MATCH_ROW_GRID = '52px 1fr 72px 1fr 315px'

interface Props {
  fixture: Fixture | EnrichedFixture
  onClick?: () => void
}

function isEnriched(f: Fixture | EnrichedFixture): f is EnrichedFixture {
  return 'has_ai_picks' in f
}

function fmtPct(v: number | null | undefined) {
  if (v == null) return null
  return `${(v * 100).toFixed(0)}%`
}

// ─── Score box ─────────────────────────────────────────────────────────────
function ScoreBox({ home, away, isLive, isFinished, kickoff, statusShort }: {
  home: number | null
  away: number | null
  isLive: boolean
  isFinished: boolean
  kickoff: dayjs.Dayjs | null
  statusShort: string | null
}) {
  if (isLive) {
    return (
      <Box style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        background: 'linear-gradient(135deg, #e8590c 0%, #f76707 100%)',
        borderRadius: 6, padding: '3px 10px', minWidth: 62,
      }}>
        <Text size="sm" fw={800} c="white" lh={1.2}>{home ?? '–'} : {away ?? '–'}</Text>
        <Text size="9px" c="rgba(255,255,255,0.85)" tt="uppercase" lh={1}>
          {statusShort === 'HT' ? 'Halbzeit' : statusShort}
        </Text>
      </Box>
    )
  }
  if (isFinished) {
    return (
      <Box style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'light-dark(#2c2c2c, #e9ecef)',
        borderRadius: 6, padding: '4px 10px', minWidth: 62,
      }}>
        <Text size="sm" fw={700} c="light-dark(white, #1a1a1a)" lh={1.2}>
          {home ?? '–'} : {away ?? '–'}
        </Text>
      </Box>
    )
  }
  // Upcoming
  return (
    <Box style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      minWidth: 62,
    }}>
      <Text size="sm" fw={700} c="dimmed" lh={1.3}>
        {kickoff ? kickoff.format('HH:mm') : '–:––'}
      </Text>
      <Text size="9px" c="var(--mantine-color-dimmed)" lh={1}>Uhr</Text>
    </Box>
  )
}

// ─── Prediction pill (ersetzt Wett-Odds) ───────────────────────────────────
function PredPill({ label, value, color = 'blue' }: {
  label: string
  value: string | null
  color?: string
}) {
  if (!value) return null
  return (
    <Box style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '2px 7px', borderRadius: 5, minWidth: 38,
      backgroundColor: `color-mix(in srgb, var(--mantine-color-${color}-6) 10%, transparent)`,
      border: `1px solid color-mix(in srgb, var(--mantine-color-${color}-6) 25%, transparent)`,
    }}>
      <Text size="9px" c={`${color}.6`} fw={600} tt="uppercase" lh={1.2}>{label}</Text>
      <Text size="xs" fw={700} c={`${color}.7`} lh={1.2}>{value}</Text>
    </Box>
  )
}

// ─── Evaluation badges (for finished games) ────────────────────────────────
function EvalBadge({ correct, label, tooltip }: { correct: boolean; label: string; tooltip?: string }) {
  const content = (
    <Box style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      padding: '1px 6px', borderRadius: 4,
      backgroundColor: correct
        ? 'color-mix(in srgb, var(--mantine-color-green-6) 12%, transparent)'
        : 'color-mix(in srgb, var(--mantine-color-red-6) 12%, transparent)',
      border: `1px solid color-mix(in srgb, var(--mantine-color-${correct ? 'green' : 'red'}-6) 30%, transparent)`,
    }}>
      <Text size="9px" fw={700} c={correct ? 'green.6' : 'red.6'} lh={1.4}>
        {correct ? '✓' : '✗'} {label}
      </Text>
    </Box>
  )
  return tooltip ? <Tooltip label={tooltip} withArrow fz="xs">{content}</Tooltip> : content
}

function EvalBadges({ ev, htScore }: { ev: FixtureEvaluation; htScore: string | null }) {
  const outcomeLabel = (o: string) => o === 'H' ? 'Heim' : o === 'D' ? 'X' : 'Aus'
  return (
    <Group gap={3} wrap="wrap" pl={4} style={{ maxWidth: 310 }}>
      <EvalBadge
        correct={ev.outcome_correct}
        label={`1X2 ${outcomeLabel(ev.predicted_outcome)}→${outcomeLabel(ev.actual_outcome)}`}
        tooltip={`Vorhergesagt: ${outcomeLabel(ev.predicted_outcome)} (${(ev.p_actual_outcome * 100).toFixed(0)}%)`}
      />
      {ev.dc_correct != null && ev.dc_prediction && (
        <EvalBadge correct={ev.dc_correct} label={`DC ${ev.dc_prediction}`} tooltip="Doppelte Chance" />
      )}
      <EvalBadge correct={ev.over_25_correct} label="O2.5" tooltip="Over/Under 2.5 Tore" />
      {ev.over_15_correct != null && (
        <EvalBadge correct={ev.over_15_correct} label="O1.5" tooltip="Over/Under 1.5 Tore" />
      )}
      <EvalBadge correct={ev.btts_correct} label="BTTS" tooltip="Beide Teams treffen" />
      {ev.home_scores_correct != null && (
        <EvalBadge correct={ev.home_scores_correct} label="H⚽" tooltip="Heimteam trifft" />
      )}
      {ev.away_scores_correct != null && (
        <EvalBadge correct={ev.away_scores_correct} label="A⚽" tooltip="Auswärtsteam trifft" />
      )}
      {htScore && (
        <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>{htScore}</Text>
      )}
    </Group>
  )
}

// ─── Main MatchRow ──────────────────────────────────────────────────────────
export function MatchRow({ fixture, onClick }: Props) {
  const isFinished = ['FT', 'AET', 'PEN'].includes(fixture.status_short ?? '')
  const isLive = ['1H', 'HT', '2H'].includes(fixture.status_short ?? '')
  const kickoff = fixture.kickoff_utc ? dayjs(fixture.kickoff_utc + 'Z') : null

  const enriched = isEnriched(fixture) ? fixture : null
  const hasProbs = enriched && (enriched.p_home_win != null || enriched.p_draw != null || enriched.p_away_win != null)
  const hasGoals = enriched && (enriched.p_goal_home != null || enriched.p_goal_away != null || enriched.p_over_15 != null)

  return (
    <Box
      onClick={onClick}
      style={{
        display: 'grid',
        gridTemplateColumns: MATCH_ROW_GRID,
        alignItems: 'center',
        gap: 0,
        padding: '7px 12px',
        cursor: onClick ? 'pointer' : 'default',
        borderRadius: 4,
        transition: 'background 0.12s',
      }}
      className="match-row"
    >
      {/* ① Zeit / Live-Indikator */}
      <Box>
        {isLive ? (
          <Box style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Text size="xs" fw={700} c="orange.6" lh={1.2}>
              {kickoff ? kickoff.format('HH:mm') : '––:––'}
            </Text>
            <Box style={{
              display: 'inline-flex', alignItems: 'center',
              backgroundColor: 'var(--mantine-color-orange-1)',
              borderRadius: 3, padding: '0 4px',
            }}>
              <Text size="9px" fw={800} c="orange.7" tt="uppercase">Live</Text>
            </Box>
          </Box>
        ) : (
          <Text size="xs" c={isFinished ? 'dimmed' : 'var(--mantine-color-text)'} fw={isFinished ? 400 : 500}>
            {kickoff ? kickoff.format('HH:mm') : '–'}
          </Text>
        )}
      </Box>

      {/* ② Heim-Team (rechts ausgerichtet) */}
      <Group justify="flex-end" gap={8} wrap="nowrap" pr={10}>
        <Text size="sm" fw={isLive ? 700 : 500} ta="right" style={{ lineHeight: 1.3 }}>
          {fixture.home_team_name}
        </Text>
        <Image
          src={teamLogoUrl(fixture.home_team_id)}
          w={26} h={26} fit="contain"
          fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
        />
      </Group>

      {/* ③ Score / Uhrzeit-Box */}
      <Box style={{ display: 'flex', justifyContent: 'center' }}>
        <ScoreBox
          home={fixture.home_score}
          away={fixture.away_score}
          isLive={isLive}
          isFinished={isFinished}
          kickoff={kickoff}
          statusShort={fixture.status_short}
        />
      </Box>

      {/* ④ Gast-Team (links ausgerichtet) */}
      <Group gap={8} wrap="nowrap" pl={10}>
        <Image
          src={teamLogoUrl(fixture.away_team_id)}
          w={26} h={26} fit="contain"
          fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
        />
        <Text size="sm" fw={isLive ? 700 : 500} style={{ lineHeight: 1.3 }}>
          {fixture.away_team_name}
        </Text>
      </Group>

      {/* ⑤ Vorhersagen */}
      <Group gap={4} wrap="nowrap" pl={12} style={{ minWidth: 0 }}>
        {hasProbs && !isFinished ? (
          <>
            <PredPill label="1" value={fmtPct(enriched!.p_home_win)} color="blue" />
            <PredPill label="X" value={fmtPct(enriched!.p_draw)} color="gray" />
            <PredPill label="2" value={fmtPct(enriched!.p_away_win)} color="teal" />
            {hasGoals && (
              <>
                <Box style={{ width: 1, height: 28, backgroundColor: 'var(--mantine-color-default-border)', margin: '0 2px' }} />
                <PredPill label="⚽H" value={fmtPct(enriched!.p_goal_home)} color="orange" />
                <PredPill label="⚽A" value={fmtPct(enriched!.p_goal_away)} color="orange" />
                {enriched!.p_over_15 != null && (
                  <PredPill label="Ü1.5" value={fmtPct(enriched!.p_over_15)} color="cyan" />
                )}
                {enriched!.p_btts != null && (
                  <PredPill label="BTTS" value={fmtPct(enriched!.p_btts)} color="violet" />
                )}
              </>
            )}
          </>
        ) : isFinished && enriched?.evaluation ? (
          <EvalBadges ev={enriched.evaluation} htScore={fixture.home_ht_score != null ? `HZ ${fixture.home_ht_score}:${fixture.away_ht_score}` : null} />
        ) : isFinished ? (
          <Text size="xs" c="dimmed" pl={4}>
            {fixture.home_ht_score != null
              ? `HZ ${fixture.home_ht_score}:${fixture.away_ht_score}`
              : ''}
          </Text>
        ) : (
          <Text size="xs" c="dimmed" pl={4}>Keine Daten</Text>
        )}

        {enriched?.has_ai_picks && !isFinished && (
          <Tooltip label="KI-Pick vorhanden" withArrow>
            <Box ml={2}>
              <IconRobot size={14} color="var(--mantine-color-violet-6)" />
            </Box>
          </Tooltip>
        )}
      </Group>
    </Box>
  )
}

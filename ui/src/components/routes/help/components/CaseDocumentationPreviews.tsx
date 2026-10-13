import { Add, People } from '@mui/icons-material';
import {
  Button,
  Card,
  Divider,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography
} from '@mui/material';
import type { Case } from 'models/entities/generated/Case';
import type { Event } from 'models/entities/generated/Event';
import type { Item } from 'models/entities/generated/Item';
import type { Rule } from 'models/entities/generated/Rule';
import type { FC } from 'react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import UserList from 'components/elements/UserList';
import { CaseEscalationControl, CaseStatusControl } from '../../cases/detail/CaseDetailControls';
import CaseOverview from '../../cases/detail/CaseOverview';
import CaseRuleRow from '../../cases/detail/CaseRuleRow';
import CaseSidebarActions from '../../cases/detail/CaseSidebarActions';
import CaseSidebarNavigation from '../../cases/detail/CaseSidebarNavigation';
import CaseTask from '../../cases/detail/CaseTask';
import CaseItemTypeSelect, { CASE_ITEM_TYPES, type CaseItemType } from '../../cases/modals/CaseItemTypeSelect';
import CaseRecordRow from '../../cases/modals/CaseRecordRow';
import CaseSelector from '../../cases/modals/CaseSelector';
import type { RecordEntry } from '../../cases/modals/types';
import FolderEntry from '../../cases/detail/sidebar/FolderEntry';

const EXAMPLE_CASE: Case = {
  __index: 'case',
  case_id: 'example-case',
  created: '2025-01-01T12:00:00Z',
  updated: '2025-01-01T12:00:00Z',
  title: 'VPN investigation',
  summary: 'Review the unusual VPN connection and related activity.',
  overview: '## Investigation notes\n\nCollect relevant evidence and document findings here.',
  status: 'in-progress',
  escalation: 'focus',
  participants: [],
  items: [
    { id: 'folder-investigation', type: 'folder', name: 'Investigation', value: 'Investigation' },
    { id: 'hit-vpn', type: 'hit', name: 'VPN Monitor', value: 'hit-vpn' }
  ],
  tasks: [{ id: 'task-review', summary: 'Review the VPN activity', complete: false }]
};

const EXAMPLE_EVENT: Event = {
  __index: 'event',
  timestamp: '2025-01-01T12:00:00Z',
  message: 'Manual evidence from VPN investigation',
  howler: { id: 'event-vpn-001', hash: 'example-hash', analytic: 'VPN Monitor' }
};

const EXAMPLE_RULE: Rule = {
  rule_id: 'example-rule',
  destination: 'alerts/{{howler.analytic}}',
  query: 'howler.analytic:Suspicious*',
  author: 'analyst',
  enabled: true,
  indexes: ['hit', 'event'],
  timeframe: 30
};

const NOOP_ASYNC = async () => {};

export const CaseNavigationPreview: FC = () => <CaseSidebarNavigation />;

export const CaseInvestigationViewsPreview: FC = () => (
  <CaseSidebarNavigation sections={['search', 'observables', 'timeline']} />
);

export const CaseControlsPreview: FC = () => (
  <CaseSidebarActions
    onAddEvent={() => {}}
    onAddItem={() => {}}
    onAddFolder={() => {}}
    onRefresh={() => {}}
    onCollapseAll={() => {}}
  />
);

export const CaseDetailsPreview: FC = () => {
  const { t } = useTranslation();
  const [status, setStatus] = useState('in-progress');
  const [escalation, setEscalation] = useState('focus');

  return (
    <Card sx={{ p: 1, width: '300px' }}>
      <Stack spacing={2}>
        <Stack spacing={1}>
          <CaseStatusControl
            value={status}
            options={['open', 'in-progress', 'on-hold', 'resolved']}
            onChange={setStatus}
          />
          <CaseEscalationControl value={escalation} options={['normal', 'focus', 'crisis']} onChange={setEscalation} />
        </Stack>
        <Divider />
        <Stack spacing={1}>
          <Stack direction="row" spacing={1} alignItems="center">
            <People />
            <Typography variant="body1">{t('page.cases.detail.participants')}</Typography>
          </Stack>
          <UserList
            multiple
            i18nLabel="page.cases.detail.assignment"
            userIds={EXAMPLE_CASE.participants ?? []}
            onChange={() => {}}
            disabled
          />
        </Stack>
      </Stack>
    </Card>
  );
};

export const CaseDashboardPreview: FC = () => <CaseOverview case={EXAMPLE_CASE} updateCase={NOOP_ASYNC} />;

export const CaseFolderTreePreview: FC = () => {
  const folder = EXAMPLE_CASE.items?.[0] as Item;
  const hit = EXAMPLE_CASE.items?.[1] as Item;

  return (
    <Paper variant="outlined" sx={{ py: 0.5, maxWidth: 350 }}>
      <FolderEntry label="Investigation" indent={0} entry={folder} chevronOpen />
      <FolderEntry label="VPN Monitor" indent={1.5} entry={hit} />
      <FolderEntry
        label="Analyst notes"
        indent={1.5}
        entry={{ id: 'notes', type: 'markdown', name: 'Analyst notes' }}
      />
    </Paper>
  );
};

export const AddRecordsPreview: FC = () => {
  const { t } = useTranslation();
  const [selectedCase, setSelectedCase] = useState<Case | null>(EXAMPLE_CASE);
  const [name, setName] = useState('VPN connection evidence');
  const entry: RecordEntry = { record: EXAMPLE_EVENT, name };
  const caseOptions = [EXAMPLE_CASE, { ...EXAMPLE_CASE, case_id: 'example-case-2', title: 'Related investigation' }];

  return (
    <Stack spacing={1} sx={{ maxWidth: 600 }}>
      <Typography variant="h4">{t('modal.cases.add_to_case')}</Typography>
      <CaseSelector options={caseOptions} value={selectedCase} onChange={setSelectedCase} />
      <CaseRecordRow entry={entry} onNameChange={setName} onParentChange={() => {}} />
      <Stack direction="row" spacing={1} alignSelf="end">
        <Button variant="outlined" color="error">
          {t('cancel')}
        </Button>
        <Button variant="outlined" color="success">
          {t('confirm')}
        </Button>
      </Stack>
    </Stack>
  );
};

export const CaseTasksPreview: FC = () => {
  const { t } = useTranslation();

  return (
    <Stack spacing={1} sx={{ maxWidth: 800 }}>
      <Typography variant="h4">{t('page.cases.dashboard.tasks')}</Typography>
      <Divider />
      <CaseTask case={EXAMPLE_CASE} task={EXAMPLE_CASE.tasks?.[0]} onEdit={NOOP_ASYNC} onDelete={NOOP_ASYNC} />
      <Stack
        onClick={() => {}}
        direction="row"
        spacing={2}
        sx={theme => ({
          borderStyle: 'dashed',
          borderColor: theme.palette.text.secondary,
          borderWidth: '0.15rem',
          borderRadius: '0.15rem',
          opacity: 0.3,
          justifyContent: 'center',
          alignItems: 'center',
          padding: 1,
          transition: theme.transitions.create('opacity'),
          '&:hover': {
            opacity: 1,
            cursor: 'pointer'
          }
        })}
      >
        <Add />
        <Typography>{t('page.cases.dashboard.tasks.add')}</Typography>
      </Stack>
    </Stack>
  );
};

export const CorrelationRulePreview: FC = () => {
  const { t } = useTranslation();

  return (
    <Paper variant="outlined" sx={{ maxWidth: 900, overflow: 'auto' }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>{t('page.cases.rules.destination')}</TableCell>
            <TableCell>{t('page.cases.rules.query')}</TableCell>
            <TableCell>{t('hit.search.index')}</TableCell>
            <TableCell>{t('page.cases.rules.timeframe')}</TableCell>
            <TableCell>{t('page.cases.rules.author')}</TableCell>
            <TableCell align="center">{t('enabled')}</TableCell>
            <TableCell align="right" />
          </TableRow>
        </TableHead>
        <TableBody>
          <CaseRuleRow rule={EXAMPLE_RULE} onToggleEnabled={() => {}} onBackfill={() => {}} onDelete={() => {}} />
        </TableBody>
      </Table>
    </Paper>
  );
};

export const CaseItemTypesPreview: FC = () => {
  const { t } = useTranslation();
  const [itemType, setItemType] = useState<CaseItemType>(CASE_ITEM_TYPES[0]);

  return (
    <Stack direction="row" spacing={1} sx={{ maxWidth: 600 }}>
      <CaseItemTypeSelect value={itemType} onChange={setItemType} />
      <TextField size="small" label={t('modal.cases.add_item.title')} fullWidth />
    </Stack>
  );
};

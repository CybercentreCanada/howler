import { Delete, History } from '@mui/icons-material';
import { Chip, IconButton, Stack, Switch, TableCell, TableRow, Tooltip, Typography } from '@mui/material';
import type { Rule } from 'models/entities/generated/Rule';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

interface CaseRuleRowProps {
  rule: Rule;
  onToggleEnabled: (enabled: boolean) => void;
  onBackfill: () => void;
  onDelete: () => void;
}

const CaseRuleRow: FC<CaseRuleRowProps> = ({ rule, onToggleEnabled, onBackfill, onDelete }) => {
  const { t } = useTranslation();

  return (
    <TableRow id={`rule-row-${rule.rule_id}`}>
      <TableCell>
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {rule.destination}
        </Typography>
      </TableCell>
      <TableCell>
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {rule.query}
        </Typography>
      </TableCell>
      <TableCell>
        <Stack direction="row" spacing={0.5}>
          {(rule.indexes ?? ['hit']).map(index => (
            <Chip key={index} size="small" label={index} variant="outlined" />
          ))}
        </Stack>
      </TableCell>
      <TableCell>
        {rule.timeframe != null ? (
          <Chip
            size="small"
            label={
              rule.expire_after_resolved
                ? t('page.cases.rules.timeframe.after_resolved', { days: rule.timeframe })
                : t('page.cases.rules.timeframe.days', { days: rule.timeframe })
            }
            color={rule.expire_after_resolved ? 'info' : 'default'}
          />
        ) : (
          <Chip size="small" label={t('page.cases.rules.no_expiry')} color="success" />
        )}
      </TableCell>
      <TableCell>
        <Typography variant="body2">{rule.author}</Typography>
      </TableCell>
      <TableCell align="center">
        <Switch
          id={`rule-toggle-${rule.rule_id}`}
          checked={rule.enabled ?? true}
          onChange={(_event, checked) => onToggleEnabled(checked)}
          size="small"
        />
      </TableCell>
      <TableCell align="right">
        <Tooltip title={t('page.cases.rules.backfill')}>
          <IconButton
            id={`rule-backfill-${rule.rule_id}`}
            size="small"
            disabled={rule.enabled === false}
            onClick={onBackfill}
          >
            <History fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={t('delete')}>
          <IconButton id={`rule-delete-${rule.rule_id}`} size="small" onClick={onDelete}>
            <Delete fontSize="small" />
          </IconButton>
        </Tooltip>
      </TableCell>
    </TableRow>
  );
};

export default CaseRuleRow;

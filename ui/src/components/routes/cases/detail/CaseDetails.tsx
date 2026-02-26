import { Check, FormatListBulleted, HourglassBottom, Pause, People, WarningRounded } from '@mui/icons-material';
import {
  Autocomplete,
  Card,
  Chip,
  Divider,
  LinearProgress,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableRow,
  TextField,
  Typography
} from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import UserList from 'components/elements/UserList';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import { useContext, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import useCase from '../hooks/useCase';
import SourceAggregate from './aggregates/SourceAggregate';

const CaseDetails: FC<{ case: Case }> = ({ case: providedCase }) => {
  const { t } = useTranslation();
  const { case: _case, updateCase } = useCase({ case: providedCase });

  const { config } = useContext(ApiConfigContext);
  const [loading, setLoading] = useState(false);

  const wrappedUpdate = async (subset: Partial<Case>) => {
    try {
      setLoading(true);
      await updateCase(subset);
    } finally {
      setLoading(false);
    }
  };

  if (!_case) {
    return (
      <Card
        sx={{
          borderRadius: 0,
          width: '300px',
          maxHeight: 'calc(100vh - 64px)',
          display: 'flex',
          flexDirection: 'column',
          p: 1
        }}
      >
        <Skeleton variant="rounded" height={50} />
      </Card>
    );
  }

  return (
    <Card
      elevation={1}
      sx={{
        borderRadius: 0,
        width: '300px',
        maxHeight: 'calc(100vh - 64px)',
        display: 'flex',
        flexDirection: 'column',
        p: 1,
        position: 'relative'
      }}
    >
      <LinearProgress sx={{ opacity: +loading, position: 'absolute', top: 0, left: 0, right: 0 }} />
      <Stack spacing={2}>
        <Stack spacing={1}>
          <Stack direction="row" spacing={1} alignItems="center">
            {{
              'in-progress': <HourglassBottom color="warning" />,
              closed: <Check color="success" />,
              'on-hold': <Pause color="disabled" />
            }[_case.status] ?? <WarningRounded fontSize="small" />}
            <Typography variant="body1">{t('page.cases.detail.status')}</Typography>
          </Stack>
          <Autocomplete
            size="small"
            disabled={loading}
            value={_case.status}
            options={config.lookups['howler.status']}
            renderInput={params => <TextField {...params} size="small" />}
            onChange={(_ev, status) => wrappedUpdate({ status })}
          />
        </Stack>
        <Divider />
        <Stack spacing={1}>
          <Stack direction="row" spacing={1} alignItems="center">
            <People />
            <Typography variant="body1">{t('page.cases.detail.participants')}</Typography>
          </Stack>
          <UserList
            buttonSx={{ alignSelf: 'start' }}
            multiple
            i18nLabel="page.cases.detail.assignment"
            userIds={_case.participants ?? []}
            onChange={participants => wrappedUpdate({ participants })}
            disabled={loading}
          />
        </Stack>
        <Divider />
        <Stack spacing={1}>
          <Stack direction="row" spacing={1} alignItems="center">
            <FormatListBulleted />
            <Typography variant="body1">{t('page.cases.detail.properties')}</Typography>
          </Stack>
          <Table sx={{ '& td': { p: 1 } }}>
            <TableBody>
              <TableRow>
                <TableCell>
                  <Typography variant="caption">{t('page.cases.escalation')}</Typography>
                </TableCell>
                <TableCell>
                  <Chip size="small" label={_case.escalation} />
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>
                  <Typography variant="caption">{t('page.cases.created')}</Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="caption">{dayjs(_case.created).toString()}</Typography>
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>
                  <Typography variant="caption">{t('page.cases.updated')}</Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="caption">{dayjs(_case.updated).toString()}</Typography>
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>
                  <Typography variant="caption">{t('page.cases.sources')}</Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="caption">
                    <SourceAggregate case={_case} />
                  </Typography>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Stack>
      </Stack>
    </Card>
  );
};

export default CaseDetails;

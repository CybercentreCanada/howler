import { ErrorOutline, ExpandMore, InfoOutlined, TaskAltOutlined } from '@mui/icons-material';
import type { AlertColor } from '@mui/material';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  AlertTitle,
  Divider,
  Stack,
  Typography
} from '@mui/material';
import Markdown from 'components/elements/display/Markdown';
import type { ActionOperation, ActionReport } from 'models/ActionTypes';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

const ActionReportDisplay: FC<{ report: ActionReport; operations: ActionOperation[] }> = ({ report, operations }) => {
  const { t } = useTranslation();

  return (
    <Stack spacing={1}>
      <Accordion variant="outlined" defaultExpanded>
        <AccordionSummary expandIcon={<ExpandMore />}>
          <Typography>{t('route.actions.report')}</Typography>
        </AccordionSummary>
        <AccordionDetails>
          {Object.entries(report).map(([operationId, _reports]) => {
            const operation = operations.find(_a => _a.id === operationId);

            if (!operation) {
              return null;
            }

            return (
              <Accordion key={operationId} variant="outlined">
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Stack direction="row" spacing={1} width="100%" mr={1}>
                    <Typography>{operation.i18nKey ? t(operation.i18nKey) : operation.title}</Typography>
                    {_reports.map(
                      r =>
                        ({
                          success: <TaskAltOutlined key={r.message} color="success" />,
                          skipped: <InfoOutlined key={r.message} color="info" />,
                          error: <ErrorOutline key={r.message} color="error" />
                        })[r.outcome]
                    )}
                  </Stack>
                </AccordionSummary>
                <AccordionDetails>
                  <Stack spacing={1}>
                    {_reports.map(r => (
                      <Alert
                        key={r.query}
                        variant="outlined"
                        severity={r.outcome.replace('skipped', 'info') as AlertColor}
                      >
                        <AlertTitle>{r.title}</AlertTitle>
                        <Stack>
                          <Typography variant="caption">
                            <Markdown md={r.message.replace('$UI_HOST', window.location.origin)} />
                          </Typography>
                          <Typography variant="caption">
                            <Link to={`/hits?query=${encodeURIComponent(r.query)}`}>
                              {t('route.actions.search.open')}
                            </Link>
                          </Typography>
                        </Stack>
                      </Alert>
                    ))}
                  </Stack>
                </AccordionDetails>
              </Accordion>
            );
          })}
        </AccordionDetails>
      </Accordion>
      <Divider orientation="horizontal" />
    </Stack>
  );
};

export default ActionReportDisplay;

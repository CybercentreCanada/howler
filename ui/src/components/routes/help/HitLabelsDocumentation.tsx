import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

import { Chip, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';
import { capitalize } from 'lodash-es';
import { LABEL_TYPES } from 'utils/constants';

const HitLabelsDocumentation: FC = () => {
  const { t } = useTranslation();

  return (
    <Stack>
      <h1>{t('help.hit.labels.title')}</h1>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>{t('page.documentation.labels.name')}</TableCell>
              <TableCell>{t('page.documentation.labels.description')}</TableCell>
              <TableCell>{t('page.documentation.labels.example')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {Object.entries(LABEL_TYPES).map(([label, details]) => (
              <TableRow key={label}>
                <TableCell>{capitalize(label)}</TableCell>
                <TableCell>{t(`hit.label.category.${label}`).replace(/.+ - /, '')}</TableCell>
                <TableCell>
                  <Chip
                    icon={details?.icon ?? undefined}
                    variant="filled"
                    size="small"
                    label={label}
                    sx={[
                      {
                        mr: 1,
                        mb: 1
                      },
                      details?.color && {
                        '&, & svg': {
                          color: theme => theme.palette.getContrastText(details.color) + ' !important'
                        },
                        backgroundColor: details.color
                      }
                    ]}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
};

export default HitLabelsDocumentation;

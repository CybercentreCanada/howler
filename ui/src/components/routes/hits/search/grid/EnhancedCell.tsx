/* eslint-disable react/no-array-index-key */
import { Stack, TableCell, type SxProps } from '@mui/material';
import PluginTypography from 'components/elements/PluginTypography';
import { memo, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const EnhancedCell: FC<{ value: string; sx?: SxProps; className: string; field: string }> = ({
  value: rawValue,
  sx = {},
  className,
  field
}) => {
  const { t } = useTranslation();

  if (!rawValue) {
    return <TableCell style={{ borderBottom: 'none' }}>{t('none')}</TableCell>;
  }

  const values = (Array.isArray(rawValue) ? rawValue : [rawValue]).filter(_value => !!_value);

  return (
    <TableCell
      sx={{ borderBottom: 'none', borderRight: 'thin solid', borderRightColor: 'divider', fontSize: '0.8rem' }}
    >
      <Stack
        direction="row"
        className={className}
        spacing={0.5}
        sx={[
          { display: 'flex', justifyContent: 'start', width: '100%', overflow: 'hidden' },
          ...(Array.isArray(sx) ? sx : [sx])
        ]}
      >
        {values.map((value, index) => (
          <PluginTypography
            context="table"
            key={value + index}
            sx={{ fontSize: 'inherit', textOverflow: 'ellipsis' }}
            value={value}
            field={field}
          >
            {value}
          </PluginTypography>
        ))}
      </Stack>
    </TableCell>
  );
};

export default memo(EnhancedCell);

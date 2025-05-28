import type { TypographyProps } from '@mui/material';
import { Typography } from '@mui/material';
import { Trans } from 'react-i18next';

type SearchTotalProps = TypographyProps & {
  total: number;
  offset: number;
  pageLength: number;
};

const SearchTotal = ({ total, offset, pageLength, ...typographyProps }: SearchTotalProps) => {
  return (
    <Typography {...typographyProps}>
      {total <= 1 ? (
        <Trans
          i18nKey="search.result.showing.single"
          values={{
            total: total
          }}
        />
      ) : (
        <Trans
          i18nKey="search.result.showing"
          values={{
            total: total,
            offset: offset + 1,
            length: pageLength + offset
          }}
        />
      )}
    </Typography>
  );
};

export default SearchTotal;

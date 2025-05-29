import type { PaginationProps } from '@mui/material';
import { Pagination } from '@mui/material';
import { useCallback } from 'react';

type SearchPaginationProps = Omit<PaginationProps, 'onChange'> & {
  limit: number;
  offset: number;
  total: number;
  onChange: (nextOffset: number) => void;
};

const SearchPagination = ({ limit, offset, total, onChange, ...paginationProps }: SearchPaginationProps) => {
  const onPageChange = useCallback(
    (_event, nextPage) => {
      onChange(nextPage === 1 ? 0 : (nextPage - 1) * limit);
    },
    [limit, onChange]
  );
  const count = Math.ceil(total / limit);
  const page = Math.floor((offset + 1) / limit) + 1;
  return limit && total && limit < total ? (
    <Pagination count={count} page={page} onChange={onPageChange} {...paginationProps} />
  ) : null;
};

export default SearchPagination;

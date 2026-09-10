import type { PaginationProps } from '@mui/material';
import { Pagination } from '@mui/material';
import type { ChangeEvent } from 'react';
import { useCallback } from 'react';

type SearchPaginationProps = Omit<PaginationProps, 'onChange'> & {
  limit: number;
  offset: number;
  total: number;
  removeCount?: number;
  onChange: (nextOffset: number) => void;
};

const SearchPagination = ({
  limit,
  offset,
  total,
  removeCount,
  onChange,
  ...paginationProps
}: SearchPaginationProps) => {
  const onPageChange = useCallback(
    (_event: ChangeEvent<unknown>, nextPage: number) => {
      onChange(nextPage === 1 ? 0 : (nextPage - 1) * limit);
    },
    [limit, onChange]
  );
  const count = Math.ceil((total + (removeCount ?? 0)) / limit);
  const page = Math.floor((offset + 1 + (removeCount ?? 0)) / limit) + 1;
  return limit && total && count > 1 ? (
    <Pagination count={count} page={page} onChange={onPageChange} {...paginationProps} />
  ) : null;
};

export default SearchPagination;

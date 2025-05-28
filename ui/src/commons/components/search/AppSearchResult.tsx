import { Box, MenuItem, MenuList, Typography, type MenuListProps } from '@mui/material';
import type { AppSearchItem } from 'commons/components/app/AppSearchService';
import { useAppSearchService } from 'commons/components/app/hooks/useAppSearchService';
import { memo, useMemo, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';

import AppListEmpty from 'commons/components/display/AppListEmpty';
import { parseEvent } from 'commons/components/utils/keyboard';

type AppSearchResultProps = MenuListProps;

const AppSearchResult = ({ className, ...menuProps }: AppSearchResultProps) => {
  const { t } = useTranslation();
  const { state, service } = useAppSearchService();

  const onKeyDown = (event: KeyboardEvent<HTMLElement>, item: AppSearchItem) => {
    const { isEnter, isEscape } = parseEvent(event);
    if (isEnter) {
      if (service.onItemSelect) {
        service.onItemSelect(item, state);
      }
    } else if (isEscape) {
      state.set({ ...state, menu: false });
    }
  };

  const options = useMemo(
    () =>
      state.items?.reduce(
        (_options, _item, index) => ({
          ..._options,
          [index]: { state, index, last: index === state.items.length - 1 }
        }),
        {}
      ),

    [state]
  );

  return (
    <div className={className}>
      <MenuList data-tui-id="tui-app-search-result" {...menuProps}>
        {state.items?.length > 0 ? (
          state.items.map((item, index) => (
            <MenuItem key={item.id} onKeyDown={event => onKeyDown(event, item)}>
              {service.itemRenderer(item, options[index])}
            </MenuItem>
          ))
        ) : state.items ? (
          <AppListEmpty />
        ) : (
          <MenuItem disabled>
            <Box mt={1} mb={1}>
              <Typography variant="body2">
                <em>{t('app.search.starttyping')}</em>
              </Typography>
            </Box>
          </MenuItem>
        )}
      </MenuList>
      {state.mode === 'inline' && service.footerRenderer && service.footerRenderer(state)}
    </div>
  );
};

export default memo(AppSearchResult);

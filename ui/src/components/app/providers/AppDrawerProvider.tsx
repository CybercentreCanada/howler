import { Drawer, Typography } from '@mui/material';
import PageContent from 'commons/components/pages/PageContent';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { AppDrawerProps } from '../drawers/AppDrawerType';

export type AppDrawerContextState = {
  close: () => void;
  open: (props: AppDrawerProps) => void;
  props: AppDrawerProps;
};

const APPDRAWER_INIT_STATE: AppDrawerContextState = {
  props: { titleKey: null, children: null, onClosed: () => null },
  close: () => null,
  open: () => null
};

export const AppDrawerContext = createContext<AppDrawerContextState>(APPDRAWER_INIT_STATE);

const AppDrawerProvider: FC<PropsWithChildren> = ({ children }) => {
  const { t } = useTranslation();

  const [isOpen, setOpen] = useState<boolean>(false);
  const [props, setProps] = useState<AppDrawerProps>(APPDRAWER_INIT_STATE.props);

  const close = useCallback(() => {
    setOpen(false);
    if (props.onClosed) {
      props.onClosed();
    }
  }, [props]);

  const open = useCallback((_props: AppDrawerProps) => {
    setOpen(true);
    setProps(_props);
  }, []);

  const context = useMemo(() => ({ props, open, close }), [props, open, close]);

  return (
    <AppDrawerContext.Provider value={context}>
      {children}
      <Drawer anchor="right" open={isOpen} PaperProps={{ sx: { minWidth: 500 } }} onClose={close}>
        <PageContent>
          <Typography variant="h4">{t(props.titleKey)}</Typography>
          {props.children}
        </PageContent>
      </Drawer>
    </AppDrawerContext.Provider>
  );
};
export default AppDrawerProvider;

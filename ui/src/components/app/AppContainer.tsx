import FlexVertical from 'components/elements/addons/layout/FlexVertical';
import type { FC } from 'react';
import { Outlet } from 'react-router-dom';
import useTitle from './hooks/useTitle';
import AppDrawerProvider from './providers/AppDrawerProvider';

const AppContainer: FC = () => {
  useTitle();

  return (
    <FlexVertical>
      <AppDrawerProvider>
        <Outlet />
      </AppDrawerProvider>
    </FlexVertical>
  );
};

export default AppContainer;

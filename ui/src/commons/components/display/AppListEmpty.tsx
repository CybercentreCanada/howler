import AppInfoPanel, { type AppInfoPanelProps } from 'commons/components/display/AppInfoPanel';

export default function AppListEmpty(props: Omit<AppInfoPanelProps, 'i18nKey'>) {
  return <AppInfoPanel {...props} i18nKey="app.list.empty" />;
}

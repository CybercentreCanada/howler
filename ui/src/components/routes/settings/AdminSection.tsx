import howlerPluginStore from 'plugins/store';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import SettingsSection from './SettingsSection';

const AdminSection: FC = () => {
  const { t } = useTranslation();
  const pluginStore = usePluginStore();

  return (
    <SettingsSection title={t('page.settings.admin.title')} colSpan={2}>
      {howlerPluginStore.plugins.map(plugin => pluginStore.executeFunction(`${plugin}.settings`, 'admin'))}
    </SettingsSection>
  );
};

export default AdminSection;

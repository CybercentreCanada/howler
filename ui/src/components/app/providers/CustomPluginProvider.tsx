import howlerPluginStore from 'plugins/store';
import type { FC, PropsWithChildren } from 'react';
import { usePluginStore } from 'react-pluggable';

const CustomPluginProvider: FC<PropsWithChildren> = ({ children }) => {
  const pluginStore = usePluginStore();

  return howlerPluginStore.plugins.reduce((_children, plugin) => {
    const Provider = pluginStore.executeFunction(`${plugin}.provider`);

    if (!Provider) {
      return _children;
    }

    return <Provider>{_children}</Provider>;
  }, children);
};

export default CustomPluginProvider;

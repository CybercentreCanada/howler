import type { Hit } from 'models/entities/generated/Hit';
import howlerPluginStore from 'plugins/store';
import { memo, type FC } from 'react';
import { usePluginStore } from 'react-pluggable';

/**
 * Plugin viewing handlers must be rendered because plugin implementations may use React hooks.
 * Memoization prevents them from running again when the surrounding hit view rerenders unchanged.
 */
const PluginViewing: FC<{ hit: Hit }> = memo(({ hit }) => {
  const pluginStore = usePluginStore();

  return <>{howlerPluginStore.plugins.map(plugin => pluginStore.executeFunction(`${plugin}.on`, 'viewing', hit))}</>;
});

export default PluginViewing;

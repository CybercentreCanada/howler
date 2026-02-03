import { Chip, type ChipProps } from '@mui/material';
import type { Hit } from 'models/entities/generated/Hit';
import howlerPluginStore from 'plugins/store';
import { type FC, type ReactNode } from 'react';
import { usePluginStore } from 'react-pluggable';

export type PluginChipProps = ChipProps & {
  value: string;
  context: string;
  field?: string;
  hit?: Hit;
};

const PluginChip: FC<PluginChipProps> = ({ children, value, context, field, hit, ...props }) => {
  const pluginStore = usePluginStore();

  for (const plugin of howlerPluginStore.plugins) {
    const component = pluginStore.executeFunction(`${plugin}.chip`, {
      children,
      value,
      context,
      field,
      hit,
      ...props
    }) as ReactNode;

    if (component) {
      return component;
    }
  }

  return <Chip {...props}>{children}</Chip>;
};

export default PluginChip;

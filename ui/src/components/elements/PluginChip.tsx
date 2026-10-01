import { Chip, type ChipProps } from '@mui/material';
import type { Hit } from 'models/entities/generated/Hit';
import howlerPluginStore from 'plugins/store';
import { createElement, type FC, type ReactNode } from 'react';
import { usePluginStore } from 'react-pluggable';

export type PluginChipProps = Omit<ChipProps, 'children'> & {
  children?: ReactNode;
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

  return createElement(Chip, { ...props, children } as any);
};

export default PluginChip;

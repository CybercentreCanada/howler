import { Typography, type TypographyProps } from '@mui/material';
import type { Hit } from 'models/entities/generated/Hit';
import howlerPluginStore from 'plugins/store';
import { memo, type FC, type ReactNode } from 'react';
import { usePluginStore } from 'react-pluggable';

export type PluginTypographyProps = TypographyProps & {
  value: string;
  context: string;
  field?: string;
  hit?: Hit;
};

const PluginTypography: FC<PluginTypographyProps> = ({ children, value, context, field, hit, ...props }) => {
  const pluginStore = usePluginStore();
  for (const plugin of howlerPluginStore.plugins) {
    const component = pluginStore.executeFunction(`${plugin}.typography`, {
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

  return <Typography {...props}>{children ?? value}</Typography>;
};

export default memo(PluginTypography);

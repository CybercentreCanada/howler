import { Typography, type TypographyProps } from '@mui/material';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import howlerPluginStore from 'plugins/store';
import { memo, type FC, type ReactNode } from 'react';
import { usePluginStore } from 'react-pluggable';

export type PluginTypographyProps = TypographyProps & {
  value: string;
  context: string;
  field?: string;
  obj?: Hit | Event;
};

const PluginTypography: FC<PluginTypographyProps> = ({ children, value, context, field, obj, ...props }) => {
  const pluginStore = usePluginStore();
  for (const plugin of howlerPluginStore.plugins) {
    const component = pluginStore.executeFunction(`${plugin}.typography`, {
      children,
      value,
      context,
      field,
      hit: obj as Hit,
      obj,
      ...props
    }) as ReactNode;

    if (component) {
      return component;
    }
  }

  return <Typography {...props}>{children ?? value}</Typography>;
};

export default memo(PluginTypography);

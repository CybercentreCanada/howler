import { Typography, type TypographyProps } from '@mui/material';
import howlerPluginStore from 'plugins/store';
import { type FC, type ReactNode } from 'react';
import { usePluginStore } from 'react-pluggable';

export type PluginTypographyProps = TypographyProps & {
  value: string;
  context: string;
};

const PluginTypography: FC<PluginTypographyProps> = ({ children, value, context, ...props }) => {
  const pluginStore = usePluginStore();

  for (const plugin of howlerPluginStore.plugins) {
    const component = pluginStore.executeFunction(`${plugin}.typography`, {
      children,
      value,
      context,
      ...props
    }) as ReactNode;

    if (component) {
      return component;
    }
  }

  return <Typography {...props}>{children}</Typography>;
};

export default PluginTypography;

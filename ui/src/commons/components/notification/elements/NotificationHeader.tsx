import { Divider, Icon, Typography, useTheme } from '@mui/material';
import React, { memo, type FC } from 'react';

type NotificationHeaderProps = {
  title: string;
  icon: React.ReactElement;
  children: React.ReactNode;
};
export const NotificationHeader: FC<NotificationHeaderProps> = memo(({ title = '', icon = null, children = null }) => {
  const theme = useTheme();
  return (
    <>
      <div
        style={{
          width: '100%',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          paddingTop: theme.spacing(2)
        }}
      >
        <Icon
          fontSize="medium"
          sx={{
            color: 'inherit',
            backgroundColor: 'inherit',
            marginLeft: theme.spacing(1.5),
            marginRight: theme.spacing(1.5)
          }}
        >
          {icon}
        </Icon>
        <Typography variant="h6" fontSize="large" fontWeight="bolder" flex={1}>
          {title}
        </Typography>
        {children}
      </div>
      <Divider orientation="horizontal" flexItem style={{ width: '100%', marginTop: theme.spacing(0.5) }} />
    </>
  );
});

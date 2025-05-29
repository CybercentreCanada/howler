import { Icon } from '@iconify/react';
import type { FC } from 'react';
import { memo } from 'react';

const ICONS = {
  hit: 'bx:target-lock',
  take: 'clarity:cursor-hand-grab-line'
};

type IconsType = keyof typeof ICONS;

const Iconified: FC<{ type: IconsType }> = ({ type }) => {
  return <Icon icon={ICONS[type]} fontSize={24} />;
};

export default memo(Iconified);

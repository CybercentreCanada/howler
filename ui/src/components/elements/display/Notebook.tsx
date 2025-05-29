import type { FC } from 'react';
import { IpynbRenderer } from 'react-ipynb-renderer';
import 'react-ipynb-renderer/dist/styles/monokai.css';

export const Notebook: FC<{ ipynb: string }> = ({ ipynb }) => {
  return <IpynbRenderer ipynb={JSON.parse(ipynb)} />;
};

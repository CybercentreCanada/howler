import { styled } from '@mui/material';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const OuterDiv = styled('div')(({ theme }) => ({
  display: 'inline-block',
  textAlign: 'center',
  width: '100%',
  margin: '30px 0',
  position: 'relative',
  '&:before': {
    content: '""',
    border: 'thin solid',
    position: 'absolute',
    left: 0,
    top: '50%',
    right: 'calc(50% + 30px)',
    borderColor: theme.palette.divider
  },
  '&:after': {
    content: '""',
    border: 'thin solid',
    position: 'absolute',
    right: 0,
    top: '50%',
    left: 'calc(50% + 30px)',
    borderColor: theme.palette.divider
  }
}));

const InnerDiv = styled('div')(() => ({
  left: '50%',
  marginLeft: '-30px',
  position: 'absolute',
  top: '-10px',
  width: '60px'
}));

const TextDivider: FC = () => {
  const { t } = useTranslation();
  return (
    <OuterDiv>
      <InnerDiv>{t('divider')}</InnerDiv>
    </OuterDiv>
  );
};

export default TextDivider;

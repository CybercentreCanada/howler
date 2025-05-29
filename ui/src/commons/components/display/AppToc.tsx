import { styled, useTheme } from '@mui/material';
import useAppBar from 'commons/components/app/hooks/useAppBar';
import useAppLayout from 'commons/components/app/hooks/useAppLayout';
import useAppUser from 'commons/components/app/hooks/useAppUser';
import React, { memo, useEffect, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';

const TocRoot = styled('div')(({ theme }) => ({
  display: 'flex',
  '.tocBar': {
    display: 'none',
    paddingLeft: '16px',
    [theme.breakpoints.up('md')]: {
      display: 'block'
    }
  },
  '.toc': {
    fontSize: '0.875rem',
    listStyle: 'none',
    paddingInlineStart: 0,
    [theme.breakpoints.only('md')]: {
      width: '124px'
    },
    [theme.breakpoints.up('lg')]: {
      width: '164px'
    },
    '& li': {
      color: theme.palette.text.primary,
      marginLeft: theme.spacing(1),
      marginBottom: theme.spacing(0.5),
      paddingLeft: theme.spacing(1.25),
      paddingRight: theme.spacing(1)
    },
    '& .active': {
      borderLeft: `solid ${theme.palette.primary.main} 2px`,
      paddingLeft: theme.spacing(1),
      color: theme.palette.primary.main
    },
    '& li:hover': {
      borderLeft: `solid ${theme.palette.text.disabled} 1px`,
      paddingLeft: '9px',
      color: theme.palette.text.disabled
    },
    '& li > a': {
      color: 'inherit',
      display: 'block',
      textDecoration: 'none',
      width: '100%'
    }
  },
  '.ttop': {
    paddingTop: theme.spacing(2.5),
    marginLeft: theme.spacing(2.25),
    color: theme.palette.text.primary,
    '& a': {
      color: 'inherit',
      display: 'block',
      textDecoration: 'none'
    },
    '& :hover': {
      color: theme.palette.text.disabled
    }
  }
}));

export type AppTocItem = {
  id: string;
  subItems?: AppTocItem[];
  is_admin?: boolean;
};

export type AppTocElementProps = {
  translation: string;
  item: AppTocItem;
};

const AppTocElement: React.FC<AppTocElementProps> = ({ translation, item }) => {
  const location = useLocation();
  const { t } = useTranslation([translation]);
  const currentHash = location.hash && location.hash !== '' ? location.hash.substring(1) : null;
  const active = currentHash && currentHash.startsWith(item.id) ? 'active' : null;
  const { user: currentUser } = useAppUser();

  return (
    (!item.is_admin || (currentUser.is_admin && item.is_admin)) && (
      <>
        <li className={active}>
          <Link to={`#${item.id}`} target="_self">
            {t(item.id)}
          </Link>
        </li>
        {active && item.subItems && (
          <ul className="toc" style={{ fontSize: 'smaller', paddingInlineStart: '8px' }}>
            {item.subItems.map(itm => (
              <AppTocElement key={itm.id} item={itm} translation={translation} />
            ))}
          </ul>
        )}
      </>
    )
  );
};

type AppTocProps = {
  children: ReactNode;
  translation: string;
  items: AppTocItem[];
  titleI18nKey?: string;
  topI18nKey?: string;
};

const AppToc = ({ children, translation, items, titleI18nKey = 'toc', topI18nKey = 'top' }: AppTocProps) => {
  const { autoHide: autoHideAppbar } = useAppBar();
  const { current: currentLayout } = useAppLayout();
  const theme = useTheme();
  const location = useLocation();
  const { t } = useTranslation([translation]);

  useEffect(() => {
    if (location.hash && location.hash !== '') {
      const scrollElement = document.getElementById(location.hash.substring(1));
      if (scrollElement) {
        // If element exists already, use native scrollIntoView.
        scrollElement.scrollIntoView(true);
      } else {
        // eslint-disable-next-line no-console
        console.log('[WARN] Trying to scroll to unknown ID:', location.hash);
      }
    }
  }, [location.hash]);

  return (
    <TocRoot id="top">
      <div id="content">{children}</div>
      <div id="toc" className="tocBar">
        <div
          style={{
            position: 'sticky',
            top: theme.spacing(autoHideAppbar && currentLayout !== 'top' ? 5 : 13)
          }}
        >
          {titleI18nKey && <div style={{ fontSize: '1.25rem', marginLeft: '18px' }}>{t(titleI18nKey)}</div>}
          <ul className="toc">
            {items && items.map(item => <AppTocElement key={item.id} item={item} translation={translation} />)}
            {topI18nKey && (
              <div className="ttop">
                <Link to="#top" target="_self">
                  {t(topI18nKey)}
                </Link>
              </div>
            )}
          </ul>
        </div>
      </div>
    </TocRoot>
  );
};

export default memo(AppToc);

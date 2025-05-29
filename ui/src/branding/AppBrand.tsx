import { Stack, useTheme } from '@mui/material';
import { useMemo } from 'react';

export const SIZES = {
  app: {
    divider: {
      margin: 12
    },
    name: {
      height: 24
    },
    icon: {
      width: 38,
      height: 38
    }
  },
  xlarge: {
    divider: {
      margin: 10
    },
    name: {
      height: 94
    },
    icon: {
      width: 150,
      height: 150
    }
  },
  large: {
    divider: {
      margin: 8
    },
    name: {
      height: 63
    },
    icon: {
      width: 100,
      height: 100
    }
  },
  medium: {
    divider: {
      margin: 6
    },
    name: {
      height: 37
    },
    icon: {
      width: 60,
      height: 60
    }
  },
  small: {
    divider: {
      margin: 4
    },
    name: {
      height: 24
    },
    icon: {
      width: 38,
      height: 38
    }
  },
  xsmall: {
    divider: {
      margin: 2
    },
    name: {
      height: 15
    },
    icon: {
      width: 24,
      height: 24
    }
  }
};

export const BRAND_APPLICATIONS = ['analyticalplatform', 'assemblyline', 'howler'] as const;

export const BRAND_SIZES = Object.keys(SIZES).filter(s => s !== 'app');

export const BRAND_VARIANTS = ['app', 'logo', 'banner-vertical', 'banner-horizontal'] as const;

export type BrandApplication = (typeof BRAND_APPLICATIONS)[number];

export type BrandVariant = (typeof BRAND_VARIANTS)[number];

export type BrandSize = (typeof BRAND_SIZES)[number];

const AppLogo = ({
  src,
  application,
  variant,
  size = 'small'
}: {
  src: string;
  application: BrandApplication;
  variant: BrandVariant;
  size?: BrandSize;
}) => {
  return (
    <img src={src} alt={`${application} logo`} style={{ ...SIZES[size].icon, marginLeft: variant === 'app' && -7 }} />
  );
};

const AppName = ({
  src,
  application,
  size = 'small'
}: {
  src: string;
  application: BrandApplication;
  size?: BrandSize;
}) => {
  return <img src={src} alt={application} style={{ ...SIZES[size].name }} />;
};

export const AppBrand = ({
  application,
  variant,
  size = 'small'
}: {
  application: BrandApplication;
  variant: BrandVariant;
  size?: BrandSize;
}) => {
  const muiTheme = useTheme();
  const theme = muiTheme.palette.mode;

  const { logoSrc, nameSrc } = useMemo(() => {
    return {
      logoSrc: `/branding/${application}/noswoosh-${theme}.svg`,
      nameSrc: `/branding/${application}/name-${theme}.svg`
    };
  }, [theme, application]);

  if (variant === 'logo') {
    return (
      <Stack direction="row" alignItems="center">
        <AppLogo application={application} src={logoSrc} variant={variant} size={size} />
      </Stack>
    );
  }

  if (variant === 'app') {
    size = 'app';
  }

  return (
    <Stack
      direction={variant.endsWith('horizontal') || variant === 'app' ? 'row' : 'column'}
      alignItems="center"
      style={{ width: 'fit-content' }}
    >
      <AppLogo application={application} src={logoSrc} variant={variant} size={size} />
      <div style={SIZES[size].divider} />
      <AppName application={application} src={nameSrc} size={size} />
    </Stack>
  );
};

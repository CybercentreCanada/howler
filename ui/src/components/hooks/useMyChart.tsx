import { useTheme } from '@mui/material';
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  SubTitle,
  TimeScale,
  Title,
  Tooltip
} from 'chart.js';
import 'chartjs-adapter-moment';
import zoomPlugin from 'chartjs-plugin-zoom';
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';

ChartJS.defaults.font.family = `'Roboto', 'Helvetica', 'Arial', sans-serif`;

ChartJS.register(
  ArcElement,
  CategoryScale,
  LinearScale,
  TimeScale,
  PointElement,
  LineElement,
  Title,
  SubTitle,
  Tooltip,
  Legend,
  CategoryScale,
  BarElement,
  Filler
);

ChartJS.register(zoomPlugin);

const useMyChart = () => {
  const { t } = useTranslation();
  const theme = useTheme();

  /**
   * Generate a basic set of default options for our graphs
   */
  const generateOptions = useCallback(
    (i18nKey: string, subtitleKey = 'route.analytics.overview.limit') => ({
      responsive: true,
      plugins: {
        legend: {
          display: true,
          position: 'top' as const,
          labels: {
            color: theme.palette.text.primary
          }
        },
        title: {
          display: true,
          text: t(i18nKey),
          color: theme.palette.text.primary,
          font: {
            size: 16
          },
          padding: {
            bottom: 0
          }
        },
        subtitle: {
          display: true,
          text: t(subtitleKey),
          color: theme.palette.text.secondary,
          font: {
            size: 10
          },
          padding: {
            bottom: 10
          }
        },
        zoom: {
          zoom: {
            wheel: {
              enabled: true,
              modifierKey: 'ctrl' as const
            },
            pinch: {
              enabled: true
            },
            mode: 'y' as const
          },
          pan: {
            enabled: true,
            mode: 'xy' as 'x' | 'y' | 'xy'
          },
          limits: {
            y: { min: 0 }
          }
        }
      },
      scales: {
        x: {
          type: 'time' as const,
          time: {
            unit: 'day' as const
          },
          ticks: {
            color: theme.palette.text.primary
          }
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: theme.palette.text.primary
          }
        }
      }
    }),
    [t, theme.palette.text.primary, theme.palette.text.secondary]
  );

  return {
    // https://www.chartjs.org/docs/latest/charts/line.html
    line: (titleKey: string, subtitleKey?: string) => {
      const options = generateOptions(titleKey, subtitleKey);

      options.plugins.subtitle = null;

      options.plugins.zoom.pan.mode = 'x';

      return options;
    },

    // https://www.chartjs.org/docs/latest/charts/doughnut.html
    doughnut: (titleKey: string, subtitleKey?: string) => {
      const options = { ...generateOptions(titleKey, subtitleKey), scales: null };

      return options;
    },

    // https://www.chartjs.org/docs/latest/charts/bar.html
    bar: (titleKey: string, subtitleKey?: string) => {
      const options = generateOptions(titleKey, subtitleKey);

      options.plugins.legend = { display: false } as any;

      options.scales = {
        y: { beginAtZero: true, ticks: { precision: 0, color: theme.palette.text.primary } },
        x: { ticks: { color: theme.palette.text.primary } }
      } as any;

      return options;
    },

    scatter: (titleKey: string, subtitleKey?: string) => {
      const options = generateOptions(titleKey, subtitleKey);

      return options;
    }
  };
};

export default useMyChart;

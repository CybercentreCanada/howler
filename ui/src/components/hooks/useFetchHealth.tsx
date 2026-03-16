import { useEffect, useState } from 'react';

export type SystemStatus = {
  name: string;
  healthy: boolean;
  importance: string;
};
const useFetchHealth = ({ pollingRateMS }: { pollingRateMS: number }) => {
  const [loading, setLoading] = useState(true);
  const [healthStatus, setHealthStatus] = useState<SystemStatus[]>([]);

  const pluginHealthUri = '/api/healthz/plugins';

  useEffect(() => {
    const getSystemHealthStatus = async () => {
      setLoading(true);
      let result: SystemStatus[] = [];

      await fetch(pluginHealthUri) // Need to use fetch instead of hget to access /api/healthz/plugins
        .then(response => response.json())
        .then(data => {
          data.forEach(({ name, healthy, importance }: SystemStatus) => {
            result.push({ name, healthy, importance });
          });
        })
        .catch(() => {
          const currentHealthStatus = healthStatus;
          result = currentHealthStatus.map(element => {
            element.healthy = false;
            return element;
          });
        });

      const sortedHealthStatus = result.sort((a, b) => a.name.localeCompare(b.name));
      setLoading(false);
      setHealthStatus(sortedHealthStatus);
    };

    getSystemHealthStatus();
    // Initial fetch and set up polling every pollingRateMS milliseconds
    const interval = setInterval(() => {
      getSystemHealthStatus();
    }, pollingRateMS);
    return () => clearInterval(interval);
  }, [pollingRateMS]);

  return { healthStatus, loading };
};

export default useFetchHealth;

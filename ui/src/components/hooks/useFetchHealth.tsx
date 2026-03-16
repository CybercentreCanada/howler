import { useEffect, useState } from 'react';

export type SystemStatus = {
  name: string;
  healthy: boolean;
  importance: string;
};
const useFetchHealth = ({ pollingRateMS, pluginHealthUri }: { pollingRateMS: number, pluginHealthUri: string }) => {
  const [loading, setLoading] = useState(true);
  const [healthStatus, setHealthStatus] = useState<SystemStatus[]>([]);


  useEffect(() => {
    const getSystemHealthStatus = async () => {
      setLoading(true);
      let result: SystemStatus[] = [];

      await fetch(pluginHealthUri) // Need to use fetch instead of hget to access /api/healthz/plugins
        .then(response => response.json())
        .then(data => {
          result = data.map(({ name, healthy, importance }: SystemStatus) => ({ name, healthy, importance }));
        })
        .catch(() => {
          const currentHealthStatus = healthStatus;
          result = currentHealthStatus.map(element => ({ ...element, healthy: false }));
        });

      result.sort((a, b) => a.name.localeCompare(b.name));
      setLoading(false);
      setHealthStatus(result);
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

import { useEffect, useState } from "react";

type Health = { status: string; environment: string; release: string };

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch("/api/health")
      .then((response) => (response.ok ? response.json() : Promise.reject(response)))
      .then(setHealth)
      .catch(() => setFailed(true));
  }, []);

  return (
    <main>
      <h1>Evolve CRM</h1>
      {health && (
        <p>
          API {health.status} · {health.environment} · release {health.release}
        </p>
      )}
      {failed && <p role="alert">The API is not reachable.</p>}
    </main>
  );
}

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

export async function request(path, token, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep the HTTP status message when the response is not JSON.
    }
    if (response.status === 401) sessionStorage.removeItem("driver-safety-token");
    throw new Error(message);
  }
  return response.json();
}

export const api = {
  login: (username, password) => request("/auth/login", null, {
    method: "POST",
    body: JSON.stringify({ username, password }),
  }),
  leaderboard: (token, order = "worst") => request(`/leaderboard?limit=100&order=${order}`, token),
  alerts: (token) => request("/alerts?limit=30", token),
  vehicle: (token, vin) => request(`/vehicles/${encodeURIComponent(vin)}`, token),
  similar: (token, vin) => request(`/vehicles/${encodeURIComponent(vin)}/similar?k=5`, token),
  ask: (token, question) => request("/agent/ask", token, {
    method: "POST",
    body: JSON.stringify({ question }),
  }),
};

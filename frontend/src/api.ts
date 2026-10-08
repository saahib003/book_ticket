const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api/v1";

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("access_token");
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${apiBaseUrl}${path}`, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (response.status === 401) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.dispatchEvent(new Event("auth:expired"));
  }
  if (!response.ok) throw new Error(body.error?.message ?? `Request failed (${response.status})`);
  return body as T;
}

export { apiBaseUrl };

/** Cliente API para hablar con el backend de FinHub. */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "finhub-dev-key-change-me";

export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "X-API-Key": API_KEY,
      "Content-Type": "application/json",
      ...options?.headers,
    },
    // Revalidar cada 15 min en SSR
    next: { revalidate: 900 },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json() as Promise<T>;
}

/** Helper para peticiones con query params. */
export function buildQuery(params: Record<string, string | number | boolean>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => search.set(k, String(v)));
  return `?${search.toString()}`;
}

/** Sube un archivo (Excel) al backend. Para el import del portfolio. */
export async function apiUpload<T>(
  path: string,
  file: File
): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY },
    body: fd,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json() as Promise<T>;
}


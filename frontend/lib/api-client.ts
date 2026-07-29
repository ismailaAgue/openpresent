/**
 * The ONLY place frontend code talks to the backend — per
 * OPENPRESENT_CODEBASE.md Section 2. Every page imports from here,
 * never calls fetch() directly against the API.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const SESSION_KEY = "op_session_token";

// NOTE: browser storage restriction (per the artifact environment's
// rules) doesn't apply here — this is a real Next.js app served from
// its own domain, not a sandboxed artifact, so localStorage is the
// correct, standard choice for a session token in a real deployment.
export function getSessionToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(SESSION_KEY);
}

export function setSessionToken(token: string) {
  window.localStorage.setItem(SESSION_KEY, token);
}

export function clearSessionToken() {
  window.localStorage.removeItem(SESSION_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getSessionToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function register(email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Registration failed");
  return res.json();
}

export async function login(email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Login failed");
  const data = await res.json();
  setSessionToken(data.session_token);
  return data;
}

export function logout() {
  clearSessionToken();
}

export async function generateSync(file: File, exportFormat = "pptx"): Promise<Blob> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/generate?export_format=${exportFormat}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Generation failed");
  return res.blob();
}

export async function generateAsync(file: File, exportFormat = "pptx") {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/generate/async?export_format=${exportFormat}`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Could not start generation");
  return res.json() as Promise<{ job_id: string; status: string }>;
}

export async function getJobStatus(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!res.ok) throw new Error("Could not check job status");
  return res.json() as Promise<{
    job_id: string; status: string; structure_source?: string;
    slide_count?: number; project_id?: string; error?: string;
  }>;
}

export function jobDownloadUrl(jobId: string) {
  return `${API_BASE}/jobs/${jobId}/download`;
}

export interface ProjectSummary {
  project_id: string;
  title: string;
  updated_at: number;
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const res = await fetch(`${API_BASE}/projects`, { headers: authHeaders() });
  if (res.status === 401) throw new Error("UNAUTHENTICATED");
  if (!res.ok) throw new Error("Could not load your projects");
  return res.json();
}

export async function getProject(projectId: string) {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, { headers: authHeaders() });
  if (res.status === 401) throw new Error("UNAUTHENTICATED");
  if (!res.ok) throw new Error("Project not found");
  return res.json() as Promise<{
    project_id: string; language: string; audience_type: string;
    slide_count: number; slides: { order: number; title: string }[];
  }>;
}

export function projectExportUrl(projectId: string, format = "pptx") {
  return `${API_BASE}/projects/${projectId}/export?export_format=${format}`;
}

export async function exportProject(projectId: string, format = "pptx"): Promise<Blob> {
  const res = await fetch(projectExportUrl(projectId, format), {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Export failed");
  return res.blob();
}

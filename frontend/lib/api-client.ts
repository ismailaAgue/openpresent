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

export async function getCurrentUser(): Promise<{ user_id: string; email: string } | null> {
  if (!getSessionToken()) return null;
  const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
  if (res.status === 401) {
    // Stale/expired token — clear it so the rest of the app stops
    // treating this as a signed-in session (Settings page's own read
    // of this function is what surfaces the problem to the user).
    clearSessionToken();
    return null;
  }
  if (!res.ok) return null;
  return res.json();
}

export interface DocumentGenerateOptions {
  exportFormat?: string;
  audienceType?: string;
  language?: string;
  targetSlideCount?: number;
  workspaceId?: string | null;  // ADR-044
}

export interface SyncGenerateResult {
  blob: Blob;
  projectId: string | null; // set only if the caller was authenticated (ADR-039)
}

export async function generateSync(file: File, opts: DocumentGenerateOptions = {}): Promise<SyncGenerateResult> {
  const form = new FormData();
  form.append("file", file);
  const params = new URLSearchParams({
    export_format: opts.exportFormat ?? "pptx",
    audience_type: opts.audienceType ?? "student_school",
    language: opts.language ?? "en",
  });
  if (opts.targetSlideCount) params.set("target_slide_count", String(opts.targetSlideCount));
  const res = await fetch(`${API_BASE}/generate?${params.toString()}`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Generation failed");
  return { blob: await res.blob(), projectId: res.headers.get("X-Project-Id") };
}

// -- AI-first: generate directly from a topic, no source document ------
// (ADR-029 — the pivot from "upload a document" to "describe what you
// want" as the primary flow; upload is kept as a second option below.)

export interface TopicGenerateOptions {
  topic: string;
  slideCount?: number;
  audienceType?: string;
  language?: string;
  tone?: string;
  exportFormat?: string;
  workspaceId?: string | null;  // ADR-044
}

function topicRequestBody(opts: TopicGenerateOptions) {
  return {
    topic: opts.topic,
    slide_count: opts.slideCount ?? 10,
    audience_type: opts.audienceType ?? "general",
    language: opts.language ?? "en",
    tone: opts.tone ?? "professional",
    export_format: opts.exportFormat ?? "pptx",
    workspace_id: opts.workspaceId ?? null,
  };
}

export async function generateFromTopicSync(opts: TopicGenerateOptions): Promise<SyncGenerateResult> {
  const res = await fetch(`${API_BASE}/generate/topic`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(topicRequestBody(opts)),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Generation failed");
  return { blob: await res.blob(), projectId: res.headers.get("X-Project-Id") };
}

export async function generateFromTopicAsync(opts: TopicGenerateOptions) {
  const res = await fetch(`${API_BASE}/generate/topic/async`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(topicRequestBody(opts)),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Could not start generation");
  return res.json() as Promise<{ job_id: string; status: string }>;
}

export async function generateAsync(file: File, opts: DocumentGenerateOptions = {}) {
  const form = new FormData();
  form.append("file", file);
  const params = new URLSearchParams({
    export_format: opts.exportFormat ?? "pptx",
    audience_type: opts.audienceType ?? "student_school",
    language: opts.language ?? "en",
  });
  if (opts.targetSlideCount) params.set("target_slide_count", String(opts.targetSlideCount));
  if (opts.workspaceId) params.set("workspace_id", opts.workspaceId);
  const res = await fetch(`${API_BASE}/generate/async?${params.toString()}`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Could not start generation");
  return res.json() as Promise<{ job_id: string; status: string }>;
}

// ADR-057 — askDocument()/Document Q&A removed (see that ADR for scope).

export async function getJobStatus(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!res.ok) throw new Error("Could not check job status");
  return res.json() as Promise<{
    job_id: string; status: string; structure_source?: string;
    slide_count?: number; project_id?: string; error?: string;
    quality_score?: number; quality_issues?: string[];
    // ADR-040 — best-effort live progress; present only while status is
    // "running". Both job types (topic generation and document upload)
    // report it, though the document path reports fewer of the 6 shared
    // stage labels since its pipeline has less internal structure.
    stage?: string;
  }>;
}

export function jobDownloadUrl(jobId: string) {
  return `${API_BASE}/jobs/${jobId}/download`;
}

export interface ProjectSummary {
  project_id: string;
  title: string;
  updated_at: number;
  workspace_id?: string | null;  // ADR-044
}

export async function listProjects(workspaceId?: string): Promise<ProjectSummary[]> {
  const url = workspaceId ? `${API_BASE}/projects?workspace_id=${workspaceId}` : `${API_BASE}/projects`;
  const res = await fetch(url, { headers: authHeaders() });
  if (res.status === 401) throw new Error("UNAUTHENTICATED");
  if (res.status === 404) throw new Error("Workspace not found");
  if (!res.ok) throw new Error("Could not load your projects");
  return res.json();
}

// -- Workspaces (ADR-044) -------------------------------------------------

export interface WorkspaceSummary {
  workspace_id: string;
  name: string;
  created_at: number;
  updated_at: number;
}

export async function listWorkspaces(): Promise<WorkspaceSummary[]> {
  const res = await fetch(`${API_BASE}/workspaces`, { headers: authHeaders() });
  if (res.status === 401) throw new Error("UNAUTHENTICATED");
  if (!res.ok) throw new Error("Could not load your workspaces");
  return res.json();
}

export async function createWorkspace(name: string): Promise<WorkspaceSummary> {
  const res = await fetch(`${API_BASE}/workspaces`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Could not create workspace");
  return res.json();
}

export async function getWorkspace(workspaceId: string) {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}`, { headers: authHeaders() });
  if (res.status === 401) throw new Error("UNAUTHENTICATED");
  if (res.status === 404) throw new Error("Workspace not found");
  if (!res.ok) throw new Error("Could not load workspace");
  return res.json() as Promise<{
    workspace_id: string; name: string; created_at: number; updated_at: number;
    projects: { project_id: string; title: string; updated_at: number }[];
  }>;
}

export async function renameWorkspace(workspaceId: string, name: string): Promise<void> {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Could not rename workspace");
}

export async function deleteWorkspace(workspaceId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Could not delete workspace");
}

// -- Brand Memory (ADR-045) ------------------------------------------------

export interface BrandProfile {
  workspace_id: string;
  name: string;
  colors: string;
  tone: string;
  audience: string;
  visual_style: string;
  updated_at?: number;
}

export async function getBrandProfile(workspaceId: string): Promise<BrandProfile> {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/brand`, { headers: authHeaders() });
  if (res.status === 401) throw new Error("UNAUTHENTICATED");
  if (res.status === 404) throw new Error("Workspace not found");
  if (!res.ok) throw new Error("Could not load brand profile");
  return res.json();
}

export async function setBrandProfile(workspaceId: string, profile: {
  name?: string; colors?: string; tone?: string; audience?: string; visual_style?: string;
}): Promise<BrandProfile> {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/brand`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    // ADR-045: this is a whole-record replace at the API/port level,
    // not a partial patch — always send the full form.
    body: JSON.stringify({
      name: profile.name ?? "", colors: profile.colors ?? "", tone: profile.tone ?? "",
      audience: profile.audience ?? "", visual_style: profile.visual_style ?? "",
    }),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Could not save brand profile");
  return res.json();
}

export async function deleteBrandProfile(workspaceId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/brand`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Could not clear brand profile");
}

export async function getProject(projectId: string) {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, { headers: authHeaders() });
  if (res.status === 401) throw new Error("UNAUTHENTICATED");
  if (!res.ok) throw new Error("Project not found");
  return res.json() as Promise<{
    project_id: string; language: string; audience_type: string;
    slide_count: number; theme: { color_set_id: string };
    slides: { order: number; title: string; bullets: string[] }[];
  }>;
}

export async function deleteProject(projectId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (res.status === 401) throw new Error("UNAUTHENTICATED");
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Could not delete this project");
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

// -- Slide-level editing / partial regeneration (ADR-038) ---------------

export interface SlideDetail {
  order: number;
  title: string;
  bullets: string[];
  notes: string;
  layout_type: string;
  image_query: string | null;
}

export async function getSlide(projectId: string, slideOrder: number): Promise<SlideDetail> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/slides/${slideOrder}`, {
    headers: authHeaders(),
  });
  if (res.status === 401) throw new Error("UNAUTHENTICATED");
  if (!res.ok) throw new Error("Slide not found");
  return res.json();
}

export async function editSlide(
  projectId: string, slideOrder: number,
  changes: { title?: string; bullets?: string[]; notes?: string }
): Promise<SlideDetail> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/slides/${slideOrder}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(changes),
  });
  if (res.status === 401) throw new Error("UNAUTHENTICATED");
  if (!res.ok) throw new Error((await res.json()).detail || "Could not save your edit");
  return res.json();
}

export async function regenerateSlide(
  projectId: string, slideOrder: number, instructions?: string
): Promise<SlideDetail> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/slides/${slideOrder}/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ instructions: instructions || null }),
  });
  if (res.status === 401) throw new Error("UNAUTHENTICATED");
  if (res.status === 503) {
    throw new Error("No AI provider is configured — try editing this slide manually instead.");
  }
  if (!res.ok) throw new Error((await res.json()).detail || "Regeneration failed");
  return res.json();
}

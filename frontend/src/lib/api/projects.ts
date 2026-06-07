import { request } from "./core";
import type {
  Chapter,
  ChapterCreatePayload,
  ProjectCreatePayload,
  ProjectCreateResponse,
  ProjectEntry,
  ProjectListItem,
  ProjectWithChapters,
} from "../../types/api";
// this stringinfies the payload and creates the response back as a promise to create the payload Project wich has chapters pages and images all kinds of information
export async function createProject(
  payload: ProjectCreatePayload,
): Promise<ProjectCreateResponse> {
  return request<ProjectCreateResponse>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listProjects(): Promise<ProjectListItem[]> {
  return request<ProjectListItem[]>("/projects");
}

export async function deleteProject(projectId: string): Promise<void> {
  await request<void>(`/projects/${projectId}`, {
    method: "DELETE",
  });
}

export async function getProject(
  projectId: string,
): Promise<ProjectWithChapters> {
  return request<ProjectWithChapters>(`/projects/${projectId}`);
}

export async function getProjectEntry(
  projectId: string,
): Promise<ProjectEntry> {
  return request<ProjectEntry>(`/projects/${projectId}/entry`);
}

export async function createProjectChapter(
  projectId: string,
  payload: ChapterCreatePayload,
): Promise<Chapter> {
  return request<Chapter>(`/projects/${projectId}/chapters`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listProjectChapters(
  projectId: string,
): Promise<Chapter[]> {
  return request<Chapter[]>(`/projects/${projectId}/chapters`);
}

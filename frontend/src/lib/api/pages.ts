import { request } from "./core";
import type {
  PageDetail,
  PageRegion,
  PageRegionPatchPayload,
  PageRegionCreatePayload,
  PageSummary,
  PageText,
  PageTextPatchPayload,
  PaginatedPageSummaryResponse,
  PageInpaintCleanupPayload,
  PageInpaintCleanupResponse,
  PsdExportRequestPayload,
  PsdExportResponse,
  ImageExportRequestPayload,
  ImageExportResponse,
} from "../../types/api";

interface ListChapterPagesOptions {
  page?: number;
  page_size?: number;
}

export async function listChapterPages(
  chapterId: string,
  options?: ListChapterPagesOptions,
): Promise<PaginatedPageSummaryResponse> {
  const query = new URLSearchParams();
  if (options?.page) {
    query.set("page", String(options.page));
  }
  if (options?.page_size) {
    query.set("page_size", String(options.page_size));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<PaginatedPageSummaryResponse>(
    `/chapters/${chapterId}/pages${suffix}`,
  );
}

export async function listAllChapterPages(
  chapterId: string,
  pageSize = 100,
): Promise<PageSummary[]> {
  const items: PageSummary[] = [];
  let page = 1;

  while (true) {
    const response = await listChapterPages(chapterId, {
      page,
      page_size: pageSize,
    });
    items.push(...response.items);
    if (!response.pagination.has_next) {
      break;
    }
    page += 1;
  }

  return items;
}

export async function getPage(pageId: string): Promise<PageDetail> {
  return request<PageDetail>(`/pages/${pageId}`);
}

export async function patchPageText(
  pageId: string,
  textId: string,
  payload: PageTextPatchPayload,
): Promise<PageText> {
  return request<PageText>(`/pages/${pageId}/texts/${textId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function patchPageRegion(
  pageId: string,
  regionId: string,
  payload: PageRegionPatchPayload,
): Promise<PageRegion> {
  return request<PageRegion>(`/pages/${pageId}/regions/${regionId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function createPageRegion(
  pageId: string,
  payload: PageRegionCreatePayload,
): Promise<PageRegion> {
  return request<PageRegion>(`/pages/${pageId}/regions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function exportPagePsd(
  pageId: string,
  payload: PsdExportRequestPayload = {},
): Promise<PsdExportResponse> {
  return request<PsdExportResponse>(`/pages/${pageId}/exports/psd`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function exportPageImage(
  pageId: string,
  payload: ImageExportRequestPayload,
): Promise<ImageExportResponse> {
  return request<ImageExportResponse>(`/pages/${pageId}/exports/image`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function savePageInpaintCleanup(
  pageId: string,
  payload: PageInpaintCleanupPayload,
): Promise<PageInpaintCleanupResponse> {
  return request<PageInpaintCleanupResponse>(`/pages/${pageId}/inpaint/cleanup`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

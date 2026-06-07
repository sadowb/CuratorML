import { request } from "./core";
import type { MaskInferenceResponse } from "../../types/api";

export async function runMaskInference(
  pageId: string,
): Promise<MaskInferenceResponse> {
  return request<MaskInferenceResponse>(`/pages/${pageId}/mask-inference`, {
    method: "POST",
  });
}

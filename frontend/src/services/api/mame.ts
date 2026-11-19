import type { MameIndexStatus, TaskExecutionResponse } from "@/__generated__";
import api from "@/services/api";
import taskApi from "@/services/api/task";

const UPDATE_TASK = "update_mame_index";

async function getIndexStatus() {
  const { data } = await api.get<MameIndexStatus>("/mame/index");
  return data;
}

async function uploadIndex(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<TaskExecutionResponse>(
    "/mame/index",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

/** Load the index from `url`, or from MAME's latest release when it is empty. */
async function updateIndex(url?: string) {
  const { data } = await taskApi.runTask(
    UPDATE_TASK,
    url ? { url } : undefined,
  );
  return data;
}

export default { getIndexStatus, uploadIndex, updateIndex };

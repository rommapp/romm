import type { Emitter } from "mitt";
import { computed, inject, onMounted, ref, watch } from "vue";
import {
  createWalkthroughForRom,
  deleteWalkthrough,
  listWalkthroughsForRom,
  uploadWalkthroughForRom,
  type StoredWalkthrough,
} from "@/services/api/walkthrough";
import type { Events } from "@/types/emitter";

type ErrorWalkthrough =
  | { response?: { data?: { detail?: string } }; message?: string }
  | null
  | undefined;

export const useUploadWalkthrough = (props: {
  romId: number;
  initialWalkthroughs?: StoredWalkthrough[];
}) => {
  const emitter = inject<Emitter<Events>>("emitter");
  const url = ref("");
  const loading = ref(false);
  const removingId = ref<number | null>(null);
  const error = ref<string | null>(null);
  const walkthroughs = ref<StoredWalkthrough[]>(
    props.initialWalkthroughs || [],
  );

  const uploadFile = ref<File | null>(null);
  const uploading = ref(false);

  const showError = (err: ErrorWalkthrough, defaultMsg: string) => {
    const detail = err?.response?.data?.detail || err?.message || defaultMsg;
    emitter?.emit("snackbarShow", {
      msg: detail,
      icon: "mdi-close-circle",
      color: "red",
    });
  };
  const showSuccess = (msg: string) => {
    emitter?.emit("snackbarShow", {
      msg,
      icon: "mdi-check-bold",
      color: "green",
    });
  };

  const hasRom = computed(() => !!props.romId);

  watch(
    () => props.initialWalkthroughs,
    (next) => {
      if (next) walkthroughs.value = next;
    },
  );

  watch(
    () => props.romId,
    () => {
      void loadWalkthroughs();
    },
  );

  async function loadWalkthroughs() {
    if (!hasRom.value) return;
    try {
      const { data } = await listWalkthroughsForRom(props.romId);
      walkthroughs.value = data;
    } catch (err) {
      console.error(err);
    }
  }

  onMounted(() => {
    void loadWalkthroughs();
  });

  async function runFetch() {
    if (!url.value) {
      emitter?.emit("snackbarShow", {
        msg: "Walkthrough URL is required",
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    }

    if (!hasRom.value) return;

    loading.value = true;
    error.value = null;

    try {
      await createWalkthroughForRom({
        romId: props.romId,
        url: url.value.trim(),
      });
      url.value = "";
      await loadWalkthroughs();
      showSuccess("Walkthrough added to ROM");
    } catch (err) {
      showError(
        err as ErrorWalkthrough,
        "Failed to add walkthrough. Please verify the URL.",
      );
    } finally {
      loading.value = false;
    }
  }

  async function uploadFileToRom() {
    if (!hasRom.value) return;
    if (!uploadFile.value) {
      emitter?.emit("snackbarShow", {
        msg: "Choose a walkthrough file (PDF, HTML, or TXT)",
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    }

    uploading.value = true;
    try {
      await uploadWalkthroughForRom({
        romId: props.romId,
        file: uploadFile.value,
      });
      uploadFile.value = null;
      await loadWalkthroughs();
      showSuccess("Walkthrough uploaded");
    } catch (err) {
      showError(err as ErrorWalkthrough, "Failed to upload walkthrough.");
    } finally {
      uploading.value = false;
    }
  }

  async function removeSavedWalkthrough(id: number) {
    removingId.value = id;
    try {
      await deleteWalkthrough(id);
      walkthroughs.value = walkthroughs.value.filter((w) => w.id !== id);
      showSuccess("Walkthrough removed");
    } catch (err) {
      showError(err as ErrorWalkthrough, "Failed to remove walkthrough.");
    } finally {
      removingId.value = null;
    }
  }

  return {
    url,
    loading,
    walkthroughs,
    uploadFile,
    uploading,
    removingId,
    runFetch,
    uploadFileToRom,
    removeSavedWalkthrough,
  };
};

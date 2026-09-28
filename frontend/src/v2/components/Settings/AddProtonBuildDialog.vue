<script setup lang="ts">
// AddProtonBuildDialog - registers a user-supplied Proton build (display
// name + tarball URL). It shows up with the other builds and is downloaded
// by the install worker on first use.
import { RBtn, RDialog, RForm, RTextField } from "@v2/lib";
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import installApi from "@/services/api/install";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const props = defineProps<{ modelValue: boolean }>();
const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "added"): void;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();

const name = ref("");
const url = ref("");
const submitting = ref(false);
const formRef = ref<InstanceType<typeof RForm> | null>(null);

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      name.value = "";
      url.value = "";
    }
  },
);

const required = (v: string) => !!v?.trim() || t("common.required");
const httpUrl = (v: string) =>
  /^https?:\/\/\S+$/i.test(v) ||
  t("settings.stream-install-custom-url-invalid");

function close() {
  emit("update:modelValue", false);
}

async function submit() {
  const result = await formRef.value?.validate();
  if (result && !result.valid) return;
  submitting.value = true;
  try {
    await installApi.addCustomProtonBuild(name.value.trim(), url.value.trim());
    snackbar.success(
      t("settings.stream-install-custom-added", { name: name.value.trim() }),
    );
    emit("added");
    close();
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string } };
      message?: string;
    };
    snackbar.error(
      t("settings.stream-install-custom-add-error", {
        detail: e?.response?.data?.detail || e?.message || "",
      }),
    );
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-plus"
    width="440"
    @update:model-value="(v) => !v && close()"
  >
    <template #header>
      <span>{{ t("settings.stream-install-custom-title") }}</span>
    </template>
    <template #content>
      <RForm ref="formRef" class="r-v2-add-proton" @submit.prevent="submit">
        <p class="r-v2-add-proton__desc">
          {{ t("settings.stream-install-custom-desc") }}
        </p>
        <RTextField
          v-model="name"
          :label="t('settings.stream-install-custom-name')"
          :rules="[required]"
          :maxlength="64"
        />
        <RTextField
          v-model="url"
          :label="t('settings.stream-install-custom-url')"
          placeholder="https://…/Proton-Custom.tar.gz"
          :rules="[required, httpUrl]"
        />
      </RForm>
    </template>
    <template #footer>
      <RBtn variant="text" :disabled="submitting" @click="close">
        {{ t("common.cancel") }}
      </RBtn>
      <RBtn
        variant="flat"
        color="primary"
        :loading="submitting"
        @click="submit"
      >
        {{ t("common.add") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-add-proton {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.r-v2-add-proton__desc {
  margin: 0;
  font-size: 13px;
  color: var(--r-color-fg-muted);
}
</style>

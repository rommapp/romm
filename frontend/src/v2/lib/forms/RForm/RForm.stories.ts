import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RBtn from "../../primitives/RBtn/RBtn.vue";
import RSelect from "../RSelect/RSelect.vue";
import RTextField from "../RTextField/RTextField.vue";
import RForm from "./RForm.vue";

const meta: Meta<typeof RForm> = {
  title: "Forms/RForm",
  component: RForm,
  argTypes: {
    disableEnterSubmit: { control: "boolean" },
    disableScrollToError: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof RForm>;

// ── Basic ──────────────────────────────────────────────────────────

export const Basic: Story = {
  name: "Basic · live validity",
  render: () => ({
    components: { RForm, RTextField, RBtn },
    setup() {
      const valid = ref(true);
      const name = ref("");
      const email = ref("");
      const submitted = ref<string | null>(null);
      const nameRules = [(v: unknown) => !!v || "Name is required"];
      const emailRules = [
        (v: unknown) => !!v || "Email is required",
        (v: unknown) => /.+@.+\..+/.test(String(v)) || "Email must be valid",
      ];
      function onSubmit() {
        submitted.value = `${name.value} <${email.value}>`;
      }
      return { valid, name, email, nameRules, emailRules, submitted, onSubmit };
    },
    template: `
      <div style="width:360px;padding:20px;background:var(--r-color-bg-elevated);border:1px solid var(--r-color-border);border-radius:12px">
        <RForm v-model="valid" @submit="onSubmit">
          <div style="display:flex;flex-direction:column;gap:12px">
            <RTextField v-model="name" prefix-label="stacked" label="Name" :rules="nameRules" placeholder="Your name" />
            <RTextField v-model="email" prefix-label="stacked" label="Email" :rules="emailRules" placeholder="you@example.com" />
            <RBtn type="submit" color="primary" :disabled="!valid">Submit</RBtn>
            <div style="font:11px sans-serif;color:var(--r-color-fg-muted)">
              Submit is enabled while the form is valid — type something invalid (e.g., a bad email) and it disables live.
            </div>
            <div v-if="submitted" style="color:var(--r-color-success);font:12px sans-serif">Submitted: {{ submitted }}</div>
          </div>
        </RForm>
      </div>
    `,
  }),
};

// ── Enter-to-submit ────────────────────────────────────────────────

export const EnterToSubmit: Story = {
  name: "Enter-to-submit",
  render: () => ({
    components: { RForm, RTextField, RBtn },
    setup() {
      const valid = ref(true);
      const value = ref("");
      const submitted = ref(0);
      const rules = [
        (v: unknown) => (String(v).length >= 3 ? true : "Too short"),
      ];
      function onSubmit() {
        submitted.value++;
      }
      return { valid, value, rules, submitted, onSubmit };
    },
    template: `
      <div style="width:360px;padding:20px;background:var(--r-color-bg-elevated);border:1px solid var(--r-color-border);border-radius:12px">
        <RForm v-model="valid" @submit="onSubmit">
          <div style="display:flex;flex-direction:column;gap:12px">
            <RTextField v-model="value" prefix-label="stacked" label="Search" :rules="rules" placeholder="Type 3+ chars and press Enter" />
            <RBtn type="submit" color="primary" :disabled="!valid">Submit</RBtn>
            <div style="font:11px sans-serif;color:var(--r-color-fg-muted)">Submitted: {{ submitted }} time(s)</div>
          </div>
        </RForm>
      </div>
    `,
  }),
};

// ── Mixed fields ───────────────────────────────────────────────────

export const MixedFields: Story = {
  name: "Mixed fields (RTextField + RSelect)",
  render: () => ({
    components: { RForm, RTextField, RSelect, RBtn },
    setup() {
      const valid = ref(true);
      const name = ref("");
      const role = ref<string | null>(null);
      const nameRules = [(v: unknown) => !!v || "Name is required"];
      const roleRules = [(v: unknown) => v != null || "Pick a role"];
      const roles = [
        { title: "Admin", value: "admin" },
        { title: "Editor", value: "editor" },
        { title: "Viewer", value: "viewer" },
      ];
      const submitted = ref<string | null>(null);
      function onSubmit() {
        submitted.value = `${name.value} (${role.value})`;
      }
      return {
        valid,
        name,
        role,
        roles,
        nameRules,
        roleRules,
        submitted,
        onSubmit,
      };
    },
    template: `
      <div style="width:380px;padding:20px;background:var(--r-color-bg-elevated);border:1px solid var(--r-color-border);border-radius:12px">
        <RForm v-model="valid" @submit="onSubmit">
          <div style="display:flex;flex-direction:column;gap:12px">
            <RTextField v-model="name" prefix-label="stacked" label="Display name" :rules="nameRules" placeholder="Jane Doe" />
            <RSelect v-model="role" :items="roles" prefix-label="stacked" label="Role" :rules="roleRules" placeholder="Pick a role" />
            <RBtn type="submit" color="primary" :disabled="!valid">Create user</RBtn>
            <div v-if="submitted" style="color:var(--r-color-success);font:12px sans-serif">Created: {{ submitted }}</div>
          </div>
        </RForm>
      </div>
    `,
  }),
};

// ── Scroll-to-error ────────────────────────────────────────────────

export const ScrollToError: Story = {
  name: "Scroll-to-error",
  render: () => ({
    components: { RForm, RTextField, RBtn },
    setup() {
      const valid = ref(true);
      const fields = ref<string[]>(["", "", "", "", "", "", "", ""]);
      const formRef = ref<{
        validate?: () => Promise<{ valid: boolean }>;
      } | null>(null);
      const rules = [(v: unknown) => !!v || "Required"];
      async function trigger() {
        await formRef.value?.validate?.();
      }
      return { valid, fields, rules, trigger, formRef };
    },
    template: `
      <div style="width:340px;padding:16px;background:var(--r-color-bg-elevated);border:1px solid var(--r-color-border);border-radius:12px;max-height:380px;overflow:auto">
        <RForm ref="formRef" v-model="valid">
          <div style="display:flex;flex-direction:column;gap:32px">
            <RTextField
              v-for="(_, i) in fields"
              :key="i"
              v-model="fields[i]"
              prefix-label="stacked"
              :label="'Field ' + (i + 1)"
              :rules="rules"
            />
            <RBtn color="primary" @click="trigger">Validate all</RBtn>
          </div>
        </RForm>
      </div>
    `,
  }),
};

// ── Reset ──────────────────────────────────────────────────────────

export const ResetForm: Story = {
  name: "Reset",
  render: () => ({
    components: { RForm, RTextField, RBtn },
    setup() {
      const valid = ref(true);
      const name = ref("");
      const email = ref("");
      const formRef = ref<{ reset?: () => void } | null>(null);
      const rules = [(v: unknown) => !!v || "Required"];
      async function clearAll() {
        formRef.value?.reset?.();
      }
      return { valid, name, email, rules, clearAll, formRef };
    },
    template: `
      <div style="width:360px;padding:20px;background:var(--r-color-bg-elevated);border:1px solid var(--r-color-border);border-radius:12px">
        <RForm ref="formRef" v-model="valid">
          <div style="display:flex;flex-direction:column;gap:12px">
            <RTextField v-model="name" prefix-label="stacked" label="Name" :rules="rules" placeholder="Jane" />
            <RTextField v-model="email" prefix-label="stacked" label="Email" :rules="rules" placeholder="you@example.com" />
            <div style="display:flex;gap:8px">
              <RBtn variant="text" @click="clearAll">Reset errors</RBtn>
              <RBtn color="primary" type="submit" :disabled="!valid">Submit</RBtn>
            </div>
            <div style="font:11px sans-serif;color:var(--r-color-fg-muted)">
              Trigger errors (blur both fields empty), then click Reset to clear them.
            </div>
          </div>
        </RForm>
      </div>
    `,
  }),
};

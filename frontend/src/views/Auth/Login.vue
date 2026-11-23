<script setup lang="ts">
// Login: thin orchestrator. Two mutually exclusive panels gated by
// `forgotMode`, each animated in/out with RExpandTransition. Login +
// OIDC sit together; the reset form replaces them when the user clicks
// "forgot password".
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import LoginForm from "@/components/Auth/LoginForm.vue";
import OIDCButton from "@/components/Auth/OIDCButton.vue";
import ResetForm from "@/components/Auth/ResetForm.vue";
import AuthCard from "@/components/shared/AuthCard.vue";
import { RDivider, RExpandTransition } from "@/lib";
import storeHeartbeat from "@/stores/heartbeat";

const heartbeatStore = storeHeartbeat();
const route = useRoute();

const {
  OIDC: {
    ENABLED: oidcEnabled,
    AUTOLOGIN: oidcAutologin,
    PROVIDER: oidcProvider,
  },
  FRONTEND: { DISABLE_USERPASS_LOGIN: loginDisabled },
} = heartbeatStore.value;

const forgotMode = ref(false);
const loginFormRef = ref<InstanceType<typeof LoginForm> | null>(null);
const oidcButtonRef = ref<InstanceType<typeof OIDCButton> | null>(null);

onMounted(() => {
  const bypassAutologin = route.query.bypass_autologin === "true";
  if (oidcEnabled && oidcAutologin && !bypassAutologin) {
    oidcButtonRef.value?.login();
  }
});
</script>

<template>
  <AuthCard>
    <!-- Login + OIDC panel -->
    <RExpandTransition>
      <div v-show="!forgotMode" class="r-login__panel">
        <LoginForm
          v-if="!loginDisabled"
          ref="loginFormRef"
          :blocking="oidcButtonRef?.loading ?? false"
          @forgot="forgotMode = true"
        />

        <template v-if="oidcEnabled">
          <RDivider v-if="!loginDisabled" class="r-login__or">
            <span>{{ $t("common.or") }}</span>
          </RDivider>
          <OIDCButton
            ref="oidcButtonRef"
            :provider="oidcProvider"
            :blocking="loginFormRef?.loggingIn ?? false"
          />
        </template>
      </div>
    </RExpandTransition>

    <!-- Forgot-password panel -->
    <RExpandTransition>
      <div v-show="forgotMode && !loginDisabled" class="r-login__panel">
        <ResetForm @done="forgotMode = false" @cancel="forgotMode = false" />
      </div>
    </RExpandTransition>
  </AuthCard>
</template>

<style scoped>
.r-login__panel {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-4);
}

.r-login__or {
  margin: var(--r-space-3) 0;
}
</style>

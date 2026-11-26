import { effectScope, type EffectScope } from "vue";

const open: EffectScope[] = [];

/** Runs a composable inside an effect scope, as a component would, so its `onScopeDispose` has a scope to register with. */
export function runInScope<T>(fn: () => T): T {
  const scope = effectScope();
  open.push(scope);
  return scope.run(fn) as T;
}

/** Stops every scope `runInScope` opened; vitest.setup.ts calls it after each test. */
export function stopScopes(): void {
  open.splice(0).forEach((scope) => scope.stop());
}

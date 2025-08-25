import { onMounted, ref } from "vue";

export function useRovingFocus(countRef: () => number) {
  const index = ref(0);
  const set = (i: number) => {
    index.value = Math.max(0, Math.min(countRef() - 1, i));
  };
  const next = () => set(index.value + 1);
  const prev = () => set(index.value - 1);

  onMounted(() => {
    // no-op placeholder for possible DOM sync
  });

  return { index, set, next, prev };
}

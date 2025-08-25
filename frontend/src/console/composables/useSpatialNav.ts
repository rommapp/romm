import type { Ref } from "vue";

export function useSpatialNav(
  selectedIndex: Ref<number>,
  getCols: () => number,
  getCount: () => number,
) {
  const moveLeft = () => {
    selectedIndex.value = Math.max(0, selectedIndex.value - 1);
  };
  const moveRight = () => {
    const cols = getCols();
    const last = getCount() - 1;
    const atRight = (selectedIndex.value + 1) % cols === 0;
    if (!atRight) selectedIndex.value = Math.min(last, selectedIndex.value + 1);
  };
  const moveUp = () => {
    const cols = getCols();
    const ni = selectedIndex.value - cols;
    if (ni >= 0) selectedIndex.value = ni;
  };
  const moveDown = () => {
    const cols = getCols();
    const ni = selectedIndex.value + cols;
    if (ni < getCount()) selectedIndex.value = ni;
  };

  return { moveLeft, moveRight, moveUp, moveDown };
}

import { ref } from "vue";

export function useElementRegistry() {
  const elements = ref<HTMLElement[]>([]);

  const registerElement = (index: number, element: HTMLElement) => {
    elements.value[index] = element;
  };

  const getElement = (index: number): HTMLElement | undefined => {
    return elements.value[index];
  };

  const clearElements = () => {
    elements.value = [];
  };

  return {
    elements,
    registerElement,
    getElement,
    clearElements,
  };
}

// Create a shared registry instance for each section
export const systemElementRegistry = useElementRegistry();
export const continuePlayingElementRegistry = useElementRegistry();
export const collectionElementRegistry = useElementRegistry();
export const smartCollectionElementRegistry = useElementRegistry();
export const virtualCollectionElementRegistry = useElementRegistry();
export const gamesListElementRegistry = useElementRegistry();

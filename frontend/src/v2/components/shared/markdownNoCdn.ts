import { h, type Component, type FunctionalComponent } from "vue";

// md-editor loads each of these renderers from unpkg on mount unless it is turned off.
const NO_CDN_PROPS = {
  noHighlight: true,
  noKatex: true,
  noMermaid: true,
  noEcharts: true,
};

/** Wraps an md-editor component so it never fetches renderers from a CDN. */
export function withoutCdn<C extends Component>(component: C): C {
  const wrapped: FunctionalComponent = (_, { attrs, slots }) =>
    h(component, { ...NO_CDN_PROPS, ...attrs }, slots);
  return wrapped as unknown as C;
}

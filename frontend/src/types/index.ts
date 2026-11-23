/* eslint-disable @typescript-eslint/no-explicit-any */

export type ExtractPiniaStoreType<D> = D extends (
  pinia?: any,
  hot?: any,
) => infer R
  ? R
  : never;

export type ValueOf<T> = T[keyof T];

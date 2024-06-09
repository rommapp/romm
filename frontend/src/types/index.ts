/* eslint-disable @typescript-eslint/no-explicit-any */

export function isKeyof<T extends object>(
  key: PropertyKey,
  obj: T,
): key is keyof T {
  return key in obj;
}

export type ExtractPiniaStoreType<D> = D extends (
  pinia?: any,
  hot?: any,
) => infer R
  ? R
  : never;

export type ValueOf<T> = T[keyof T];

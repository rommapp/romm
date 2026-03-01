export type FormInputField<
  T extends Record<string, unknown>,
  K extends keyof T = keyof T,
> = readonly [key: K, value: T[K], filename?: string];

export function buildFormInput<T extends Record<string, unknown>>(
  fields: ReadonlyArray<FormInputField<T>>,
): FormData {
  const formData = new FormData();

  fields.forEach(([key, value, filename]) => {
    if (value === undefined || value === null) return;

    const formKey = String(key);
    if (value instanceof Blob) {
      if (filename) {
        formData.append(formKey, value, filename);
      } else {
        formData.append(formKey, value);
      }
      return;
    }

    formData.append(formKey, String(value));
  });

  return formData;
}

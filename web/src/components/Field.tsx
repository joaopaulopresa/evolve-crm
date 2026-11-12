import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

type InputProps = { label: string } & InputHTMLAttributes<HTMLInputElement>;
export const TextField = ({ label, ...props }: InputProps) => (
  <Field label={label}>
    <input {...props} />
  </Field>
);

type SelectProps = { label: string; children: ReactNode } & SelectHTMLAttributes<HTMLSelectElement>;
export const SelectField = ({ label, children, ...props }: SelectProps) => (
  <Field label={label}>
    <select {...props}>{children}</select>
  </Field>
);

type AreaProps = { label: string } & TextareaHTMLAttributes<HTMLTextAreaElement>;
export const TextAreaField = ({ label, ...props }: AreaProps) => (
  <Field label={label}>
    <textarea rows={3} {...props} />
  </Field>
);

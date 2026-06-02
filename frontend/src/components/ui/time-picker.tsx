import * as React from "react";

import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";

export type TimePickerProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> & {
  stepMinutes?: 1 | 5 | 10 | 15 | 30 | 60;
};

function TimePicker({ className, stepMinutes = 5, ...props }: TimePickerProps) {
  const stepSeconds = stepMinutes * 60;
  return (
    <Input
      type="time"
      step={stepSeconds}
      className={cn(
        "supports-[font-variant-numeric:tabular-nums]:font-[family-name:var(--font-geist-mono)] supports-[font-variant-numeric:tabular-nums]:tabular-nums",
        className,
      )}
      {...props}
    />
  );
}

export { TimePicker };

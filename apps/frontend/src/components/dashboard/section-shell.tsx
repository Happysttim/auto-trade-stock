import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type SectionShellProps = {
  title: string;
  description?: string;
  eyebrow?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function SectionShell({
  title,
  description,
  eyebrow,
  actions,
  children,
  className,
}: SectionShellProps) {
  return (
    <section
      className={cn(
        "rounded-[1.5rem] bg-background/45 p-5 shadow-[0_18px_48px_rgba(15,23,42,0.06)]",
        className,
      )}
    >
      <div className="flex flex-col gap-4 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-1.5">
          {eyebrow ? (
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">{eyebrow}</p>
          ) : null}
          <h2 className="text-xl font-semibold text-foreground">{title}</h2>
          {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
      </div>
      <div>{children}</div>
    </section>
  );
}

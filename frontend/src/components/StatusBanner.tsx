import type { ReactNode } from "react";

interface StatusBannerProps {
  tone: "info" | "warning" | "error" | "success";
  title?: string;
  children: ReactNode;
  onDismiss?: () => void;
}

export function StatusBanner({
  tone,
  title,
  children,
  onDismiss,
}: StatusBannerProps) {
  return (
    <div className={`banner banner-${tone}`} role={tone === "error" ? "alert" : "status"}>
      <div className="banner-body">
        {title ? <strong>{title}</strong> : null}
        <div>{children}</div>
      </div>
      {onDismiss ? (
        <button type="button" className="banner-close" onClick={onDismiss} aria-label="Dismiss">
          x
        </button>
      ) : null}
    </div>
  );
}

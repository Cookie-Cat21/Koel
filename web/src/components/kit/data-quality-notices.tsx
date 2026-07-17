import {
  AlertTriangle,
  FileWarning,
  Info,
  type LucideIcon,
} from "lucide-react";

import { AlertBanner } from "@/components/kit/alert-banner";
import type {
  DataQualityNotice,
  DataQualityTone,
} from "@/lib/data-quality";
import { cn } from "@/lib/utils";

const ICONS: Record<DataQualityTone, LucideIcon> = {
  info: Info,
  warning: AlertTriangle,
  danger: FileWarning,
};

/**
 * Stack of data-quality banners for symbol pages — why price/filings/briefs
 * look empty or thin, without implying the UI is broken.
 */
export function DataQualityNotices({
  notices,
  className,
}: {
  notices: DataQualityNotice[];
  className?: string;
}) {
  if (notices.length === 0) return null;

  return (
    <div
      className={cn("mt-4 flex flex-col gap-3", className)}
      data-testid="data-quality-notices"
      aria-label="Data quality notices"
    >
      {notices.map((notice) => (
        <AlertBanner
          key={notice.id}
          tone={notice.tone}
          icon={ICONS[notice.tone]}
          title={notice.title}
          description={notice.description}
        />
      ))}
    </div>
  );
}

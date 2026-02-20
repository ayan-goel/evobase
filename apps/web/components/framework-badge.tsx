import {
  getFrameworkIconPath,
  getFrameworkLabel,
  getPmIconPath,
  getPmLabel,
} from "@/lib/framework-meta";

interface FrameworkBadgeProps {
  framework: string | null;
  packageManager?: string | null;
  size?: "sm" | "md";
  showLabel?: boolean;
}

const SIZE_PX: Record<"sm" | "md", number> = { sm: 14, md: 20 };

function IconImg({
  src,
  title,
  px,
}: {
  src: string;
  title: string;
  px: number;
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={title}
      title={title}
      width={px}
      height={px}
      className="invert opacity-80"
      style={{ width: px, height: px }}
    />
  );
}

export function FrameworkBadge({
  framework,
  packageManager,
  size = "sm",
  showLabel = false,
}: FrameworkBadgeProps) {
  const px = SIZE_PX[size];
  const fwLabel = getFrameworkLabel(framework);
  const fwIcon = getFrameworkIconPath(framework);

  return (
    <span className="flex items-center gap-1.5 flex-wrap">
      <span className="flex items-center gap-1" title={fwLabel}>
        <IconImg src={fwIcon} title={fwLabel} px={px} />
        {showLabel && (
          <span
            className={
              size === "md"
                ? "text-xs text-white/60"
                : "text-xs text-white/50"
            }
          >
            {fwLabel}
          </span>
        )}
      </span>

      {packageManager && (
        <span
          className="flex items-center gap-1"
          title={getPmLabel(packageManager)}
        >
          <IconImg
            src={getPmIconPath(packageManager)}
            title={getPmLabel(packageManager)}
            px={SIZE_PX["sm"]}
          />
          <span className="text-xs text-white/30">{packageManager}</span>
        </span>
      )}
    </span>
  );
}

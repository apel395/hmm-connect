import clsx from "clsx";
import Spinner from "./Spinner";

export interface LoadingProps {
  message?: string;
  fullScreen?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export default function Loading({
  message = "Loading...",
  fullScreen = false,
  size = "md",
  className,
}: LoadingProps) {
  const content = (
    <div
      className={clsx(
        "flex flex-col items-center justify-center gap-3 py-8",
        className
      )}
    >
      <Spinner size={size} />
      <p className="text-sm text-slate-500">{message}</p>
    </div>
  );

  if (!fullScreen) {
    return content;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/80 backdrop-blur-sm">
      {content}
    </div>
  );
}

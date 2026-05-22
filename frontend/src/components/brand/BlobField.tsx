import { cn } from "@/lib/utils";

interface Props {
  density?: "sparse" | "full";
  className?: string;
}

/** Five fixed-position gradient blobs. CSS-only, no animation. */
export function BlobField({ density = "full", className }: Props) {
  const showAll = density === "full";
  return (
    <div className={cn("blob-field", className)} aria-hidden="true">
      <span className="blob b1" style={{ width: 220, height: 140, top: "8%",  right: "10%", transform: "rotate(18deg)" }} />
      <span className="blob b2" style={{ width: 170, height: 170, top: "26%", right: "32%", transform: "rotate(-22deg)" }} />
      <span className="blob b3" style={{ width: 240, height: 120, top: "48%", right: "6%",  transform: "rotate(16deg)" }} />
      {showAll && (
        <span className="blob b4" style={{ width: 140, height: 140, top: "62%", right: "26%", transform: "rotate(-10deg)" }} />
      )}
      {showAll && (
        <span className="blob b5" style={{ width: 200, height: 110, top: "80%", right: "14%", transform: "rotate(22deg)" }} />
      )}
    </div>
  );
}

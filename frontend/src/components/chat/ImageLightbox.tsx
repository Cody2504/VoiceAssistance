import { useEffect } from "react";
import { X } from "lucide-react";

interface Props {
  /** Image source (data URL or http URL). When null, the lightbox is closed. */
  src: string | null;
  onClose: () => void;
}

/**
 * Full-size image preview overlay — the image-equivalent of `VideoPreviewModal`.
 * Click the backdrop or the close button (or press Escape) to dismiss. Reuses the
 * shared `overlay-in` / `modal-pop` animation classes for visual consistency.
 */
export function ImageLightbox({ src, onClose }: Props) {
  useEffect(() => {
    if (!src) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [src, onClose]);

  if (!src) return null;
  return (
    <div className="overlay-in fixed inset-0 z-50 grid place-items-center bg-black/70 p-6" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="modal-pop relative max-h-[90vh] max-w-[90vw]">
        <button
          onClick={onClose}
          className="absolute -right-3 -top-3 z-10 grid h-8 w-8 place-items-center rounded-full bg-black/70 text-white shadow transition duration-150 ease-out hover:bg-black/90 active:scale-95"
        >
          <X size={16} />
        </button>
        <img src={src} alt="" className="max-h-[90vh] max-w-[90vw] rounded-lg object-contain" />
      </div>
    </div>
  );
}

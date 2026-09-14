import { useState, type CSSProperties } from "react";

/** Neutral inline placeholder — no network request, legible on both themes. */
const PLACEHOLDER =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 88 88" fill="none" stroke="#8E8C8C" stroke-width="3" stroke-linejoin="round">` +
    `<rect x="16" y="16" width="56" height="56" rx="6"/><path d="m16 58 16-18 32 32"/><circle cx="53" cy="35" r="7"/></svg>`,
  );

interface ProductImageProps {
  src: string;
  alt: string;
  /** cover fills the box (catalog cards); contain shows the whole product (chat cards). */
  fit?: "cover" | "contain";
  /** Above-the-fold images should load immediately; everything else defers until near the viewport. */
  eager?: boolean;
  style?: CSSProperties;
}

/**
 * Every product photo goes through here so loading behaviour is consistent:
 * lazy by default, decoded off the main thread, and a quiet placeholder
 * instead of the browser's broken-image icon when a remote host fails.
 */
export function ProductImage({ src, alt, fit = "cover", eager = false, style }: ProductImageProps) {
  const [failed, setFailed] = useState(false);
  return (
    <img
      src={failed ? PLACEHOLDER : src}
      alt={alt}
      loading={eager ? "eager" : "lazy"}
      decoding="async"
      onError={() => setFailed(true)}
      style={{
        width: "100%",
        height: "100%",
        objectFit: failed ? "contain" : fit,
        objectPosition: "center",
        display: "block",
        padding: failed ? "22%" : undefined,
        ...style,
      }}
    />
  );
}

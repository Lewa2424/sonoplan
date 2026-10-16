import { useEffect, useState, type RefObject } from "react";

export function useElementSize(ref: RefObject<HTMLElement | null>): {
  width: number;
  height: number;
} {
  const [size, setSize] = useState({ width: 320, height: 280 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      setSize({
        width: Math.max(Math.floor(width), 200),
        height: Math.max(Math.floor(height), 200),
      });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);

  return size;
}

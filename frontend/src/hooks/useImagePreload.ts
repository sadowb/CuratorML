import { useEffect, useState } from "react";


export function useImagePreload(imageUrl: string | undefined) {
  const [displayedUrl, setDisplayedUrl] = useState(imageUrl ?? "");
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    if (!imageUrl) {
      setDisplayedUrl("");
      setHasError(false);
      setIsLoading(false);
      return;
    }

    if (imageUrl === displayedUrl) return;

    let cancelled = false;
    const img = new Image();

    setIsLoading(true);

    const swap = () => {
      if (cancelled) return;
      setDisplayedUrl(imageUrl);
      setHasError(false);
      setIsLoading(false);
    };

    img.onload = swap;
    img.onerror = () => {
      if (cancelled) return;
      if (!displayedUrl) setHasError(true);
      setIsLoading(false);
    };

    img.decoding = "async";
    img.src = imageUrl;
    if (typeof img.decode === "function") {
      void img.decode().then(swap).catch(() => {});
    }

    return () => { cancelled = true; };
  }, [displayedUrl, imageUrl]);

  return { displayedUrl, isLoading, hasError };
}

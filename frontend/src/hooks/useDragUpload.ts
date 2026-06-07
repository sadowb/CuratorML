import { useCallback, useRef, useState, type DragEvent } from "react";


export function useDragUpload(
  onDrop: (files: FileList) => void,
) {
  const [isDragActive, setIsDragActive] = useState(false);
  const depthRef = useRef(0);

  const hasFiles = (e: DragEvent<HTMLElement>) =>
    Array.from(e.dataTransfer.types).includes("Files");

  const onDragEnter = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depthRef.current += 1;
      setIsDragActive(true);
    },
    [],
  );

  const onDragOver = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    },
    [],
  );

  const onDragLeave = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depthRef.current = Math.max(depthRef.current - 1, 0);
      if (depthRef.current === 0) setIsDragActive(false);
    },
    [],
  );

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depthRef.current = 0;
      setIsDragActive(false);
      onDrop(e.dataTransfer.files);
    },
    [onDrop],
  );

  return {
    isDragActive,
    dragHandlers: {
      onDragEnter,
      onDragOver,
      onDragLeave,
      onDrop: handleDrop,
    },
  };
}

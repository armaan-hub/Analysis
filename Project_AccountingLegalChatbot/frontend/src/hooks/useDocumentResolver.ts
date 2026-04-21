import { useCallback, useMemo } from 'react';

export interface SourceDocLike {
  id: string;
  filename: string;
  original_name?: string;
}

export function useDocumentResolver(docs: SourceDocLike[] | undefined) {
  const docMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const doc of docs ?? []) {
      const display = doc.original_name ?? doc.filename;
      map[doc.id] = display;
      map[doc.filename] = display;
      if (doc.original_name) map[doc.original_name] = display;
    }
    return map;
  }, [docs]);

  const resolve = useCallback(
    (source: string): string => docMap[source] ?? source,
    [docMap],
  );

  return { resolve, docMap };
}

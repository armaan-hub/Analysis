import { useCallback, useMemo } from 'react';

export interface SourceDocLike {
  id: string;
  filename: string;
  original_name: string;
}

export function useDocumentResolver(docs: SourceDocLike[] | undefined) {
  const docMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const doc of docs ?? []) {
      map[doc.id] = doc.original_name;
      map[doc.filename] = doc.original_name;
      map[doc.original_name] = doc.original_name;
    }
    return map;
  }, [docs]);

  const resolve = useCallback(
    (source: string): string => docMap[source] ?? source,
    [docMap],
  );

  return { resolve, docMap };
}

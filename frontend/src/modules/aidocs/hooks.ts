import { useMutation, useQuery, useQueryClient, useInfiniteQuery } from "@tanstack/react-query";
import { aidocsService } from "@/services/aidocsService";

export function useAiStatus() {
  return useQuery({ queryKey: ["aidocs", "status"], queryFn: aidocsService.status, staleTime: 60_000 });
}

export function useAiDocsTemplates() {
  return useQuery({ queryKey: ["aidocs", "templates"], queryFn: aidocsService.templates });
}

export function useAiDocsDocuments(search?: string) {
  // P2 из аудита 22.08.2026 ("Добавить pagination во все потенциально
  // большие списки"): backend уже поддерживает page/page_size
  // (см. GET /api/v1/aidocs/documents), useInfiniteQuery — идиоматичный
  // React Query способ отдать фронтенду "Показать ещё" без ручного
  // управления состоянием страницы.
  return useInfiniteQuery({
    queryKey: ["aidocs", "documents", search ?? ""],
    queryFn: ({ pageParam }) => aidocsService.documents(search, pageParam),
    initialPageParam: 1,
    getNextPageParam: (lastPage, allPages) => {
      // Backend отдаёt page_size=100 по умолчанию (см. router) — если
      // последняя страница набрала меньше этого, следующей точно нет
      // смысла запрашивать (последняя строка, а не 100 = полная).
      const DEFAULT_PAGE_SIZE = 100;
      return lastPage.length < DEFAULT_PAGE_SIZE ? undefined : allPages.length + 1;
    },
  });
}

export function useAiDocsDocument(id: string | null) {
  return useQuery({
    queryKey: ["aidocs", "document", id],
    queryFn: () => aidocsService.document(id as string),
    enabled: !!id,
  });
}

export function useAiDocsActiveConversation() {
  return useQuery({
    queryKey: ["aidocs", "active-conversation"],
    queryFn: () => aidocsService.activeConversation(),
    // Не троттлим агрессивно — это лёгкий GET, а актуальность (есть ли
    // черновик прямо сейчас) важнее кеша.
    staleTime: 0,
  });
}

export function useAiDocsVersions(id: string | null) {
  return useQuery({
    queryKey: ["aidocs", "versions", id],
    queryFn: () => aidocsService.versions(id as string),
    enabled: !!id,
  });
}

export function useRestoreAiDocVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, versionId }: { id: string; versionId: string }) => aidocsService.restoreVersion(id, versionId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["aidocs", "document", vars.id] });
      qc.invalidateQueries({ queryKey: ["aidocs", "versions", vars.id] });
      qc.invalidateQueries({ queryKey: ["aidocs", "documents"] });
    },
  });
}

export function useCompareAiDocVersions() {
  return useMutation({
    mutationFn: ({ id, fromVersionId, toVersionId }: { id: string; fromVersionId: string; toVersionId: string }) =>
      aidocsService.compareVersions(id, fromVersionId, toVersionId),
  });
}

export function useAnalyzeAiDoc() {
  return useMutation({
    mutationFn: (id: string) => aidocsService.analyze(id),
  });
}

export function useCreateAiDoc() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: aidocsService.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aidocs", "documents"] }),
  });
}

export function useDeleteAiDoc() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: aidocsService.remove,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aidocs", "documents"] }),
  });
}

export function useToggleAiDocFavorite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, is_favorite }: { id: string; is_favorite: boolean }) => aidocsService.setFavorite(id, is_favorite),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aidocs", "documents"] }),
  });
}

export function useRenameAiDoc() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => aidocsService.rename(id, title),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["aidocs", "documents"] });
      qc.invalidateQueries({ queryKey: ["aidocs", "document", vars.id] });
    },
  });
}

export function useDuplicateAiDoc() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: aidocsService.duplicate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aidocs", "documents"] }),
  });
}

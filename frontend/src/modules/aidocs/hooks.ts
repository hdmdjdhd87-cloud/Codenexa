import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { aidocsService } from "@/services/aidocsService";

export function useAiStatus() {
  return useQuery({ queryKey: ["aidocs", "status"], queryFn: aidocsService.status, staleTime: 60_000 });
}

export function useAiDocsTemplates() {
  return useQuery({ queryKey: ["aidocs", "templates"], queryFn: aidocsService.templates });
}

export function useAiDocsDocuments(search?: string) {
  return useQuery({
    queryKey: ["aidocs", "documents", search ?? ""],
    queryFn: () => aidocsService.documents(search),
  });
}

export function useAiDocsDocument(id: string | null) {
  return useQuery({
    queryKey: ["aidocs", "document", id],
    queryFn: () => aidocsService.document(id as string),
    enabled: !!id,
  });
}

export function useAiDocsVersions(id: string | null) {
  return useQuery({
    queryKey: ["aidocs", "versions", id],
    queryFn: () => aidocsService.versions(id as string),
    enabled: !!id,
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

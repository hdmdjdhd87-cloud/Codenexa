import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { settingsService } from "@/services/settingsService";

export function useSettings() {
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: ["settings"],
    queryFn: settingsService.get,
  });

  const update = useMutation({
    mutationFn: settingsService.update,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  return { ...query, update };
}

import { useQuery } from "@tanstack/react-query";
import { moduleService } from "@/services/moduleService";

export function useModules() {
  return useQuery({
    queryKey: ["modules"],
    queryFn: moduleService.listActive,
    staleTime: 30_000,
  });
}

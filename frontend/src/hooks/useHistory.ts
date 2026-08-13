import { useQuery } from "@tanstack/react-query";
import { historyService } from "@/services/historyService";

export function useHistory(page = 1) {
  return useQuery({
    queryKey: ["history", page],
    queryFn: () => historyService.list(page),
  });
}

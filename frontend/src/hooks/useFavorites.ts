import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { favoriteService } from "@/services/favoriteService";

export function useFavorites() {
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: ["favorites"],
    queryFn: favoriteService.list,
    staleTime: 15_000,
  });

  const add = useMutation({
    mutationFn: favoriteService.add,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorites"] }),
  });

  const remove = useMutation({
    mutationFn: favoriteService.remove,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorites"] }),
  });

  return { ...query, add, remove };
}

import { useQuery } from "@tanstack/react-query";
import { userService } from "@/services/userService";

export function useCurrentUser() {
  return useQuery({
    queryKey: ["me"],
    queryFn: userService.me,
    retry: 1,
  });
}

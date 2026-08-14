import { useEffect, useState } from "react";

/** Задержка перед применением значения (например, поискового запроса),
 * чтобы не гонять фильтрацию на каждое нажатие клавиши. */
export function useDebouncedValue<T>(value: T, delayMs = 250): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}

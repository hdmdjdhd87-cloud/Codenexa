const TOKEN_KEY = "codenexa.session_token";

/**
 * localStorage используется здесь только как UI-кэш, чтобы не логиниться
 * заново при каждом ре-рендере. Единственный источник истины о валидности
 * токена — backend (подпись и exp JWT). Если токен невалиден, любой
 * защищённый запрос вернёт 401, и apiClient обязан удалить его и заново
 * пройти авторизацию через Telegram initData.
 */
export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // localStorage недоступен (приватный режим и т.п.) — работаем без кэша.
  }
}

export function clearStoredToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

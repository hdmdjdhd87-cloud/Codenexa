import { clearStoredToken, getStoredToken, setStoredToken } from "./tokenStorage";
import { getInitData } from "./telegram";
import type { ApiErrorBody } from "@/types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const REQUEST_TIMEOUT_MS = 12000;

export class ApiClientError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await promise;
  } finally {
    clearTimeout(timer);
  }
}

let reauthPromise: Promise<string> | null = null;

async function authenticateWithTelegram(): Promise<string> {
  const initData = getInitData();
  if (!initData) {
    throw new ApiClientError(401, "NO_TELEGRAM_CONTEXT", "Приложение открыто вне Telegram — авторизация невозможна.");
  }
  const resp = await fetch(`${API_BASE_URL}/api/v1/auth/telegram`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ init_data: initData }),
  });
  const body = await resp.json().catch(() => null);
  if (!resp.ok || !body?.token) {
    const err = body as ApiErrorBody | null;
    throw new ApiClientError(
      resp.status,
      err?.error?.code ?? "AUTH_FAILED",
      err?.error?.message ?? "Не удалось авторизоваться."
    );
  }
  setStoredToken(body.token);
  return body.token as string;
}

async function ensureToken(forceReauth = false): Promise<string> {
  const existing = getStoredToken();
  if (existing && !forceReauth) return existing;

  if (!reauthPromise) {
    reauthPromise = authenticateWithTelegram().finally(() => {
      reauthPromise = null;
    });
  }
  return reauthPromise;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Публичные эндпоинты (например /health) не требуют токен */
  skipAuth?: boolean;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, skipAuth = false } = options;

  const doFetch = async (token: string | null): Promise<Response> => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      return await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timer);
    }
  };

  let token: string | null = null;
  if (!skipAuth) {
    token = await ensureToken();
  }

  let resp: Response;
  try {
    resp = await doFetch(token);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiClientError(0, "TIMEOUT", "Превышено время ожидания ответа сервера.");
    }
    throw new ApiClientError(0, "NETWORK_ERROR", "Нет соединения. Проверьте интернет.");
  }

  // Токен истёк/невалиден — переавторизуемся один раз и повторяем запрос.
  if (resp.status === 401 && !skipAuth) {
    clearStoredToken();
    const freshToken = await ensureToken(true);
    resp = await doFetch(freshToken);
  }

  if (!resp.ok) {
    const errBody = (await resp.json().catch(() => null)) as ApiErrorBody | null;
    throw new ApiClientError(
      resp.status,
      errBody?.error?.code ?? "REQUEST_FAILED",
      errBody?.error?.message ?? "Что-то пошло не так. Попробуйте ещё раз."
    );
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

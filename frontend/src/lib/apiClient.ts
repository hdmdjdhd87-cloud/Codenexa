import { clearStoredToken, getStoredToken, setStoredToken } from "./tokenStorage";
import { getInitData } from "./telegram";
import type { ApiErrorBody } from "@/types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const REQUEST_TIMEOUT_MS = 12000;
// Экспорт DOCX/PDF (особенно с OCR/AI-шагами) может занимать дольше
// обычного JSON-эндпоинта — отдельный, более щедрый бюджет для скачивания.
const DOWNLOAD_TIMEOUT_MS = 30000;
// F-012 из аудита 22.08.2026: не более ОДНОГО повтора для foreground-
// запроса — иначе худший случай (несколько полных таймаутов подряд)
// делает UI ощутимо зависшим вместо просто медленного.
const MAX_ATTEMPTS = 2;

export class ApiClientError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/**
 * F-012 из аудита: раньше retry применялся только к запросу
 * авторизации, обычные apiRequest-вызовы падали с первого сбоя.
 * Правило безопасного повтора (буквально по формулировке аудита):
 * "Retry только идемпотентные операции или операции с Idempotency-Key".
 *  - GET/HEAD — всегда безопасно (по определению не мутирует).
 *  - POST/PATCH/DELETE — только если вызывающий код сам передал
 *    Idempotency-Key (значит backend умеет дедуплицировать повтор).
 *  - Из статусов: сетевые ошибки/таймауты и 5xx — временные, стоит
 *    повторить; 429 — тоже (с уважением к серверному состоянию, не
 *    агрессивно); ЛЮБОЙ другой 4xx — НЕ повторяем, это семантическая
 *    ошибка запроса, повтор ничего не изменит и может быть вредным.
 */
export function shouldRetryRequest(method: string, status: number | null, hasIdempotencyKey: boolean): boolean {
  const isSafeMethod = method === "GET" || method === "HEAD";
  if (!isSafeMethod && !hasIdempotencyKey) return false;

  if (status === null) return true; // сетевая ошибка/таймаут — не HTTP-статус вовсе
  if (status === 429) return true;
  if (status >= 500) return true;
  return false; // остальные 4xx — не временные, повтор не поможет
}

/**
 * Экспоненциальный backoff + jitter (аудит явно требует jitter — без
 * него множество клиентов, упавших одновременно, повторят запрос
 * синхронно и создадут ту же самую перегрузку заново, "retry storm").
 * attempt: 0 для первой попытки (обычно не вызывается для неё), 1+ для
 * повторов. Капается сверху, чтобы не улететь в минуты ожидания.
 */
export function computeBackoffDelayMs(attempt: number): number {
  const base = Math.min(400 * 2 ** (attempt - 1), 4000);
  const jitter = Math.random() * base * 0.5;
  return Math.round(base + jitter);
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

async function fetchWithRetry(url: string, init: RequestInit, attempts = 3): Promise<Response> {
  let lastErr: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      const resp = await fetch(url, init);
      // 5xx часто означает временную проблему на сервере (холодный старт
      // контейнера, кратковременная недоступность БД) — тоже стоит
      // повторить, а не сразу сдаваться после первого же ответа.
      if (resp.status >= 500 && i < attempts - 1) {
        await new Promise((r) => setTimeout(r, computeBackoffDelayMs(i + 1)));
        continue;
      }
      return resp;
    } catch (err) {
      lastErr = err;
      if (i < attempts - 1) {
        await new Promise((r) => setTimeout(r, computeBackoffDelayMs(i + 1))); // короткий backoff перед повтором
      }
    }
  }
  throw lastErr;
}

async function authenticateWithTelegram(): Promise<string> {
  const initData = getInitData();
  if (!initData) {
    throw new ApiClientError(401, "NO_TELEGRAM_CONTEXT", "Приложение открыто вне Telegram — авторизация невозможна.");
  }

  let resp: Response;
  try {
    resp = await fetchWithRetry(`${API_BASE_URL}/api/v1/auth/telegram`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: initData }),
    });
  } catch {
    // Раньше сырая "Failed to fetch" всплывала на экран как есть (см. п.17
    // спецификации). Теперь — понятная ошибка + один автоматический повтор
    // уже был сделан внутри fetchWithRetry перед тем, как сдаться.
    throw new ApiClientError(
      0,
      "NETWORK_ERROR",
      "Не удалось подключиться к CodeNexa. Проверьте интернет и попробуйте снова."
    );
  }

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
  /** Дополнительные заголовки — например Idempotency-Key (п.7 промпта) */
  headers?: Record<string, string>;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, skipAuth = false, headers: extraHeaders } = options;
  const hasIdempotencyKey = !!extraHeaders?.["Idempotency-Key"];

  const doFetch = async (token: string | null): Promise<Response> => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      return await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...extraHeaders,
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

  // F-012: безопасный повтор (см. shouldRetryRequest) вместо падения с
  // первого же сетевого сбоя/5xx. MAX_ATTEMPTS=2 — один повтор, не
  // цепочка из нескольких полных таймаутов подряд.
  let resp: Response | null = null;
  let lastNetworkError: unknown = null;
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    lastNetworkError = null;
    try {
      resp = await doFetch(token);
    } catch (err) {
      lastNetworkError = err;
      resp = null;
    }

    const status = resp?.status ?? null;
    const isLastAttempt = attempt === MAX_ATTEMPTS - 1;
    if (isLastAttempt || !shouldRetryRequest(method, status, hasIdempotencyKey)) break;

    await new Promise((r) => setTimeout(r, computeBackoffDelayMs(attempt + 1)));
  }

  if (!resp) {
    if (lastNetworkError instanceof DOMException && lastNetworkError.name === "AbortError") {
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

/**
 * Скачивание бинарных файлов (DOCX/PDF), которые требуют авторизации.
 * Обычная <a href> не может передать заголовок Authorization — поэтому
 * тут ручной fetch + blob + программный клик по временной ссылке.
 *
 * F-013 из аудита 22.08.2026: раньше здесь не было ни таймаута, ни
 * восстановления после истёкшего токена — зависший запрос мог висеть
 * бесконечно, а протухший токен просто падал с ошибкой вместо тихого
 * обновления, как это уже работает в apiRequest.
 */
export async function downloadAuthorizedFile(path: string, filenameFallback: string): Promise<void> {
  const doFetch = async (token: string): Promise<Response> => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), DOWNLOAD_TIMEOUT_MS);
    try {
      return await fetch(`${API_BASE_URL}${path}`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timer);
    }
  };

  const token = await ensureToken();
  let resp: Response;
  try {
    resp = await doFetch(token);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiClientError(0, "TIMEOUT", "Превышено время ожидания — файл не удалось скачать.");
    }
    throw new ApiClientError(0, "NETWORK_ERROR", "Нет соединения. Проверьте интернет.");
  }

  if (resp.status === 401) {
    clearStoredToken();
    const freshToken = await ensureToken(true);
    try {
      resp = await doFetch(freshToken);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new ApiClientError(0, "TIMEOUT", "Превышено время ожидания — файл не удалось скачать.");
      }
      throw new ApiClientError(0, "NETWORK_ERROR", "Нет соединения. Проверьте интернет.");
    }
  }

  if (!resp.ok) {
    const errBody = (await resp.json().catch(() => null)) as ApiErrorBody | null;
    throw new ApiClientError(
      resp.status,
      errBody?.error?.code ?? "DOWNLOAD_FAILED",
      errBody?.error?.message ?? "Не удалось скачать файл."
    );
  }
  const blob = await resp.blob();
  const disposition = resp.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : filenameFallback;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

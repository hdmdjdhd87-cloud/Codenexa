import { colorFromString } from "@/lib/colorFromString";

interface AvatarProps {
  photoUrl?: string | null;
  name: string;
  size?: number;
}

/**
 * Единый компонент аватара для всего приложения (Главная, Профиль,
 * будущие модули). Использует Telegram photo_url, если он есть; иначе
 * генерирует стабильный (по имени) fallback-круг с инициалом — без
 * повторных загрузок одного и того же изображения (п.6 спецификации).
 */
export function Avatar({ photoUrl, name, size = 44 }: AvatarProps) {
  const initial = (name || "?").trim().charAt(0).toUpperCase();
  const style = { width: size, height: size, fontSize: Math.round(size * 0.42) };
  const color = colorFromString(name || "?");

  if (photoUrl) {
    return (
      <img
        src={photoUrl}
        alt={name}
        style={style}
        className="rounded-2xl object-cover border border-border shrink-0"
        loading="lazy"
      />
    );
  }

  return (
    <div
      style={{ ...style, background: color.tint, color: color.bg }}
      className="rounded-2xl flex items-center justify-center font-semibold border border-border shrink-0"
      aria-label={name}
    >
      {initial}
    </div>
  );
}

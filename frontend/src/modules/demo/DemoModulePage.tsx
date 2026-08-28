import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import t from "@/i18n";
import { hideBackButton, showBackButton } from "@/lib/telegram";

/**
 * CodeNexa Demo — минимальный тестовый модуль (п.14, п.55 спецификации).
 * Существует только для проверки жизненного цикла Module Registry:
 * регистрация → появление в каталоге → открытие → BackButton →
 * попадание в историю → добавление в избранное → возврат в Core.
 *
 * Соответствующая запись реестра создаётся в
 * migrations/0002_nexa_seed_demo_module.sql, а не хардкодится здесь —
 * сам модуль лишь предоставляет UI по своему route ("/apps/codenexa-demo").
 */
export function DemoModulePage() {
  const navigate = useNavigate();

  useEffect(() => {
    const onBack = () => navigate("/catalog");
    showBackButton(onBack);
    return () => hideBackButton(onBack);
  }, [navigate]);

  return (
    <div className="px-4 pt-8 pb-6 flex flex-col items-center text-center">
      <div className="w-16 h-16 rounded-2xl bg-accent/15 border border-accent/30 flex items-center justify-center text-accent mb-5">
        <CheckCircle2 size={28} aria-hidden="true" />
      </div>
      <h1 className="text-text-primary text-[19px] font-semibold">{t("demoModule.title")}</h1>
      <p className="text-text-secondary text-cn-md mt-2 max-w-[280px]">{t("demoModule.message")}</p>
    </div>
  );
}

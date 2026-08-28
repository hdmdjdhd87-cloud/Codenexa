import { useRef, useState } from "react";
import { Camera } from "lucide-react";
import { haptic } from "@/lib/telegram";
import { aidocsService, type AiDocsTemplate } from "@/services/aidocsService";
import { useCreateAiDoc } from "../hooks";

export function CreateDocumentView({
  template,
  onCreated,
}: {
  template: AiDocsTemplate;
  onCreated: (id: string) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrText, setOcrText] = useState<string | null>(null);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [suggestedFields, setSuggestedFields] = useState<Record<string, string>>({});
  const create = useCreateAiDoc();
  const submittingRef = useRef(false);

  function setField(key: string, value: string) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  async function handlePhotoUpload(file: File) {
    setOcrError(null);
    setOcrText(null);
    setSuggestedFields({});
    setOcrLoading(true);
    haptic("light");
    try {
      const result = await aidocsService.ocr(file, template.id);
      setOcrText(result.text || "");
      setSuggestedFields(result.suggested_fields || {});
      if (!result.text) {
        setOcrError("Текст на изображении не распознан. Попробуйте более чёткое фото.");
      }
    } catch (e) {
      setOcrError(e instanceof Error ? e.message : "Не удалось распознать изображение.");
    } finally {
      setOcrLoading(false);
    }
  }

  function applyAllSuggestions() {
    setValues((v) => ({ ...v, ...suggestedFields }));
    haptic("success");
  }

  async function handleSubmit() {
    // Синхронный guard (useRef, не useState) — блокирует повторный вызов
    // ДО следующего рендера, закрывая ту же гонку двойного тапа, которую
    // одно только disabled на кнопке не успевает поймать (п.7 промпта).
    if (submittingRef.current) return;
    submittingRef.current = true;
    setError(null);
    haptic("light");
    try {
      const doc = await create.mutateAsync({
        template_id: template.id,
        title: template.name,
        field_values: values,
      });
      haptic("success");
      onCreated(doc.id);
    } catch (e) {
      haptic("error");
      setError(e instanceof Error ? e.message : "Не удалось создать документ.");
    } finally {
      submittingRef.current = false;
    }
  }

  return (
    <div>
      <h3 className="text-text-primary text-cn-lg font-semibold mb-1">{template.name}</h3>
      <p className="text-text-secondary text-cn-sm mb-4">Заполните данные — документ соберётся автоматически.</p>

      {/* Загрузка фото/скана: настоящий OCR (Tesseract), без AI-понимания
          структуры — честно распознаёт текст, пользователь сам переносит
          нужное в поля ниже. */}
      <div className="rounded-xl bg-surface border border-border p-3.5 mb-4">
        <label className="flex items-center justify-center gap-2 py-2.5 rounded-lg border border-dashed border-border text-text-secondary text-cn-sm font-medium cursor-pointer">
          <Camera size={16} aria-hidden="true" /> Загрузить фото/скан для распознавания текста
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handlePhotoUpload(file);
              e.target.value = "";
            }}
          />
        </label>
        {ocrLoading && <p className="text-text-secondary text-[12px] mt-2">Распознаём текст…</p>}
        {ocrError && <p className="text-error text-[12px] mt-2">{ocrError}</p>}
        {ocrText && (
          <div className="mt-2.5">
            <p className="text-text-secondary text-[11px] mb-1">
              Распознанный текст (автоматическое понимание структуры целиком требует AI, пока недоступно — но
              сумму/срок/дату/телефон/email ниже уже удалось сопоставить с полями):
            </p>
            <div className="rounded-lg bg-surface-elevated p-2.5 text-[12px] text-text-primary whitespace-pre-wrap max-h-32 overflow-y-auto">
              {ocrText}
            </div>
            {Object.keys(suggestedFields).length > 0 && (
              <div className="mt-2.5 rounded-lg bg-accent/10 border border-accent/30 p-2.5 flex items-center justify-between gap-2">
                <p className="text-text-primary text-[12px]">
                  Найдено полей для автозаполнения: {Object.keys(suggestedFields).length}
                </p>
                <button onClick={applyAllSuggestions} className="shrink-0 text-accent text-[12px] font-semibold">
                  Заполнить всё
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-3">
        {template.fields_schema.map((field) => (
          <div key={field.key}>
            <label className="block text-text-secondary text-[12px] font-medium mb-1.5">
              {field.label}
              {field.required && <span className="text-error"> *</span>}
            </label>
            {field.type === "textarea" ? (
              <textarea
                value={values[field.key] || ""}
                onChange={(e) => setField(field.key, e.target.value)}
                rows={4}
                className="w-full rounded-xl bg-surface border border-border px-3.5 py-2.5 text-cn-base text-text-primary outline-none focus:border-accent resize-none"
              />
            ) : (
              <input
                type={field.type === "date" ? "date" : "text"}
                value={values[field.key] || ""}
                onChange={(e) => setField(field.key, e.target.value)}
                className="w-full rounded-xl bg-surface border border-border px-3.5 py-2.5 text-cn-base text-text-primary outline-none focus:border-accent"
              />
            )}
            {suggestedFields[field.key] && suggestedFields[field.key] !== values[field.key] && (
              <button
                onClick={() => setField(field.key, suggestedFields[field.key])}
                className="mt-1.5 text-cn-xs text-accent font-medium"
              >
                Использовать из фото: «{suggestedFields[field.key]}»
              </button>
            )}
          </div>
        ))}
      </div>

      {error && <p className="text-error text-cn-sm mt-3">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={create.isPending}
        className="w-full mt-5 py-3.5 rounded-2xl bg-accent text-white font-semibold text-cn-md disabled:opacity-60"
      >
        {create.isPending ? "Создаём…" : "Создать документ"}
      </button>
    </div>
  );
}

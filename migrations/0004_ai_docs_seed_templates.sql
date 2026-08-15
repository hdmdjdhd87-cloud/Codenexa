-- ============================================================
-- CodeNexa System — AI Docs seed 0004
-- Реальные шаблоны: каждый имеет полную fields_schema и body_template,
-- каждый реально генерирует DOCX/PDF через document_engine — ни одной
-- "красивой карточки, которая ничего не делает" (п.23/44 спецификации).
-- ============================================================

insert into nexa_docs_templates (template_key, name, category, description, fields_schema, body_template, sort_order)
values
(
  'business-letter',
  'Деловое письмо',
  'business',
  'Официальное письмо организации или должностному лицу.',
  '[
    {"key":"recipient_title","label":"Кому (должность, ФИО)","type":"text","required":true},
    {"key":"sender_name","label":"От кого (ФИО, должность)","type":"text","required":true},
    {"key":"subject","label":"Тема письма","type":"text","required":true},
    {"key":"body","label":"Текст письма","type":"textarea","required":true},
    {"key":"city","label":"Город","type":"text","required":false},
    {"key":"date","label":"Дата","type":"date","required":true}
  ]'::jsonb,
  '[
    {"type":"paragraph_right","text":"{{recipient_title}}"},
    {"type":"spacer"},
    {"type":"heading","text":"{{subject}}"},
    {"type":"paragraph","text":"{{body}}"},
    {"type":"spacer"},
    {"type":"paragraph","text":"{{city}}, {{date}}"},
    {"type":"signature_line","text":"{{sender_name}}"}
  ]'::jsonb,
  1
),
(
  'application-statement',
  'Заявление',
  'personal',
  'Стандартное заявление на имя должностного лица.',
  '[
    {"key":"recipient_title","label":"Кому (должность, ФИО)","type":"text","required":true},
    {"key":"sender_name","label":"От кого (ФИО)","type":"text","required":true},
    {"key":"body","label":"Текст заявления","type":"textarea","required":true},
    {"key":"city","label":"Город","type":"text","required":false},
    {"key":"date","label":"Дата","type":"date","required":true}
  ]'::jsonb,
  '[
    {"type":"paragraph_right","text":"{{recipient_title}}"},
    {"type":"paragraph_right","text":"от {{sender_name}}"},
    {"type":"spacer"},
    {"type":"heading_center","text":"ЗАЯВЛЕНИЕ"},
    {"type":"paragraph","text":"{{body}}"},
    {"type":"spacer"},
    {"type":"paragraph","text":"{{city}}, {{date}}"},
    {"type":"signature_line","text":"{{sender_name}}"}
  ]'::jsonb,
  2
),
(
  'receipt',
  'Расписка',
  'personal',
  'Расписка о получении денежных средств или имущества.',
  '[
    {"key":"receiver_name","label":"ФИО получателя (кто пишет расписку)","type":"text","required":true},
    {"key":"receiver_id","label":"Паспортные данные получателя","type":"text","required":false},
    {"key":"giver_name","label":"ФИО передающей стороны","type":"text","required":true},
    {"key":"amount","label":"Сумма / имущество","type":"text","required":true},
    {"key":"purpose","label":"Основание передачи","type":"textarea","required":false},
    {"key":"city","label":"Город","type":"text","required":false},
    {"key":"date","label":"Дата","type":"date","required":true}
  ]'::jsonb,
  '[
    {"type":"heading_center","text":"РАСПИСКА"},
    {"type":"spacer"},
    {"type":"paragraph","text":"Я, {{receiver_name}} ({{receiver_id}}), получил(а) от {{giver_name}} следующее: {{amount}}."},
    {"type":"paragraph","text":"Основание: {{purpose}}"},
    {"type":"spacer"},
    {"type":"paragraph","text":"{{city}}, {{date}}"},
    {"type":"signature_line","text":"{{receiver_name}}"}
  ]'::jsonb,
  3
),
(
  'service-agreement',
  'Договор оказания услуг',
  'business',
  'Договор между заказчиком и исполнителем на оказание услуг.',
  '[
    {"key":"customer_name","label":"Заказчик (ФИО/организация)","type":"text","required":true},
    {"key":"contractor_name","label":"Исполнитель (ФИО/организация)","type":"text","required":true},
    {"key":"service_description","label":"Предмет договора (описание услуги)","type":"textarea","required":true},
    {"key":"price","label":"Стоимость услуг","type":"text","required":true},
    {"key":"term","label":"Срок оказания услуг","type":"text","required":true},
    {"key":"city","label":"Город заключения","type":"text","required":false},
    {"key":"date","label":"Дата заключения","type":"date","required":true}
  ]'::jsonb,
  '[
    {"type":"heading_center","text":"ДОГОВОР ОКАЗАНИЯ УСЛУГ"},
    {"type":"paragraph","text":"{{city}}, {{date}}"},
    {"type":"spacer"},
    {"type":"paragraph","text":"{{customer_name}}, именуемый(ая) в дальнейшем «Заказчик», и {{contractor_name}}, именуемый(ая) в дальнейшем «Исполнитель», заключили настоящий договор о нижеследующем:"},
    {"type":"heading","text":"1. Предмет договора"},
    {"type":"paragraph","text":"{{service_description}}"},
    {"type":"heading","text":"2. Стоимость и срок"},
    {"type":"paragraph","text":"Стоимость услуг составляет: {{price}}. Срок оказания услуг: {{term}}."},
    {"type":"spacer"},
    {"type":"signature_line","text":"Заказчик: {{customer_name}}"},
    {"type":"signature_line","text":"Исполнитель: {{contractor_name}}"}
  ]'::jsonb,
  4
)
on conflict (template_key) do nothing;

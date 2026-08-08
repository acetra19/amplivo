-- Systeme.io / solopreneur email sequences (DE)
-- Step 1 = curiosity / question ONLY (no affiliate link).
-- Link soft-introduced from step 2+.
-- Placeholders: {{first_name}} {{company}} {{industry}} {{sender_name}} {{affiliate_url}}

UPDATE email_sequence_steps AS s
SET
  subject_tpl = v.subject_tpl,
  body_tpl = v.body_tpl
FROM email_sequences AS es,
LATERAL (VALUES
  (1, 'Kurze Frage zu {{company}}',
   E'Hallo {{first_name}},\n\nkurz zu {{company}}: womit baust du aktuell Funnels, E-Mail und Kurszugang – ein Tool oder mehrere?\n\nIch frage, weil viele Solo-Setups dort unnötig Zeit verlieren. Kein Pitch, nur die eine Frage.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Kein Interesse an solchen Mails? Antworte mit STOP.'),
  (2, 'Re: Kurze Frage zu {{company}}',
   E'Hallo {{first_name}},\n\nkurz nachgehakt zur Tool-Frage.\n\nFalls du gerade mehrere Tools fuer Funnel/E-Mail/Kurse nutzt: Systeme.io hat einen Free-Plan ohne Kreditkarte – oft reicht der zum Testen.\n\nOptional anschauen:\n{{affiliate_url}}\n\nWenn es nicht passt, einfach ignorieren.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Antworte STOP zum Abmelden.'),
  (3, 'Letzte Nachricht – {{company}}',
   E'Hallo {{first_name}},\n\nletzte Mail von mir. Wenn Stack gerade kein Thema ist: alles gut.\n\nFalls du doch vereinfachen willst – Free-Zugang ohne Kreditkarte:\n{{affiliate_url}}\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Antworte STOP zum Abmelden.')
) AS v(step_order, subject_tpl, body_tpl)
WHERE s.sequence_id = es.id
  AND es.slug = 'outbound_a'
  AND s.step_order = v.step_order;

UPDATE email_sequence_steps AS s
SET
  subject_tpl = v.subject_tpl,
  body_tpl = v.body_tpl
FROM email_sequences AS es,
LATERAL (VALUES
  (1, 'Kurze Frage an {{company}}',
   E'Hallo {{first_name}},\n\nbei {{company}} interessiert mich kurz: laeuft bei dir Funnel + E-Mail + Kurs schon in einem System – oder noch getrennt?\n\nNur diese eine Frage, kein Link, kein Call.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Antworte STOP zum Abmelden.'),
  (2, 'Re: Tool-Setup {{company}}',
   E'Hallo {{first_name}},\n\nnur ein kurzer Reminder.\n\nWenn getrennte Tools nerven: Free-Plan von Systeme.io (Funnels + E-Mail + Kurse) zum Ausprobieren:\n{{affiliate_url}}\n\nKein Abo-Zwang. Falls uninteressant – ignorieren.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Antworte STOP zum Abmelden.')
) AS v(step_order, subject_tpl, body_tpl)
WHERE s.sequence_id = es.id
  AND es.slug = 'nurture_b'
  AND s.step_order = v.step_order;

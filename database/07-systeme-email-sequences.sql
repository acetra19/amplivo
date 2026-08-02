-- Systeme.io / solopreneur email sequences (DE primary, soft link early)
-- Safe to re-run. Placeholders: {{first_name}} {{company}} {{industry}} {{sender_name}} {{affiliate_url}}

UPDATE email_sequence_steps AS s
SET
  subject_tpl = v.subject_tpl,
  body_tpl = v.body_tpl
FROM email_sequences AS es,
LATERAL (VALUES
  (1, 'Kurze Frage zu {{company}}',
   E'Hallo {{first_name}},\n\nich habe gesehen, dass {{company}} im Online-Business unterwegs ist. Viele Coaches und Creator zahlen noch fuer 3–5 separate Tools (Funnels, E-Mail, Kurse, Zahlungen).\n\nSysteme.io buendelt das in einer Plattform – der Free-Plan geht ohne Kreditkarte.\n\nCTA: Free-Zugang starten (1 Klick, keine Kreditkarte):\n{{affiliate_url}}\n\nOder antworte kurz mit deiner groessten Tool-Frage.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Kein Interesse mehr? Antworte einfach mit STOP.'),
  (2, 'Re: Kurze Frage zu {{company}}',
   E'Hallo {{first_name}},\n\nkurz nachgehakt – falls du noch mit mehreren Tools jonglierst:\n\nCTA: Free-Plan oeffnen:\n{{affiliate_url}}\n\nKein Pitch-Druck. Wenn es gerade nicht passt, einfach ignorieren.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Antworte STOP zum Abmelden.'),
  (3, 'Letzte Nachricht – {{company}}',
   E'Hallo {{first_name}},\n\nletzte Mail von mir. Wenn Stack-Vereinfachung gerade keine Prioritaet ist: alles gut.\n\nFalls doch – CTA: Free-Zugang ohne Kreditkarte:\n{{affiliate_url}}\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Antworte STOP zum Abmelden.')
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
  (1, 'Idee fuer {{company}}: weniger Tools, mehr Fokus',
   E'Hallo {{first_name}},\n\nviele {{industry}}-Gruender starten mit 4–5 Tools und verlieren Zeit an Setup statt an Kunden.\n\nPraktischer Start: Systeme.io Free-Plan (Funnels + E-Mail + Kurse).\n\nCTA: Hier kostenlos starten:\n{{affiliate_url}}\n\nWenn du willst, antworte mit deinem aktuellen Setup – ich sage dir ehrlich, ob es passt.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Antworte STOP zum Abmelden.'),
  (2, 'Re: weniger Tools fuer {{company}}',
   E'Hallo {{first_name}},\n\nnur ein kurzer Reminder.\n\nCTA: Free-Zugang oeffnen:\n{{affiliate_url}}\n\nKein Abo-Zwang. Falls uninteressant – einfach ignorieren.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. Antworte STOP zum Abmelden.')
) AS v(step_order, subject_tpl, body_tpl)
WHERE s.sequence_id = es.id
  AND es.slug = 'nurture_b'
  AND s.step_order = v.step_order;

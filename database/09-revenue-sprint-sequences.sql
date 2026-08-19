-- Paid 48h setup offer CTAs (point to /setup). Curiosity step 1 still link-free.

UPDATE email_sequence_steps AS s
SET
  subject_tpl = v.subject_tpl,
  body_tpl = v.body_tpl
FROM email_sequences AS es,
LATERAL (VALUES
  (1, 'Kurze Frage zu {{company}}',
   E'Hallo {{first_name}},\n\nkurz zu {{company}}: laeuft dein Verkauf aktuell ueber eine klare Opt-in-Seite + automatische E-Mail – oder noch manuell / ueber mehrere Tools?\n\nNur diese eine Frage.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. STOP zum Abmelden.'),
  (2, 'Re: Kurze Frage zu {{company}}',
   E'Hallo {{first_name}},\n\nkurz nachgehakt.\n\nFalls Funnel + E-Mail noch Zeit fressen: wir setzen das in 48 Stunden fertig um (Opt-in, Danke-Seite, Welcome-Mail) – Fixpreis 197 EUR.\n\nDetails: https://www.amplivo.net/setup\n\nWenn du willst: antworte BUY – dann schicken wir die Rechnung per Mail.\n(Optional DIY-Tool-Link: {{affiliate_url}})\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. STOP zum Abmelden.'),
  (3, 'Letzte Nachricht – 48h Setup {{company}}',
   E'Hallo {{first_name}},\n\nletzte Mail.\n\n48h Funnel-Setup fuer {{company}} – 197 EUR Fixpreis:\nhttps://www.amplivo.net/setup\n\nAntworte BUY oder ignorieren.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. STOP zum Abmelden.')
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
   E'Hallo {{first_name}},\n\nbei {{company}}: hast du schon eine einfache Funnel-Seite mit automatischer Follow-up-Mail – oder noch nicht?\n\nNur die Frage.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. STOP zum Abmelden.'),
  (2, 'Re: Tool-Setup {{company}}',
   E'Hallo {{first_name}},\n\nfalls Setup gerade nervt: 48h Fertigstellung (Opt-in + Mail) fuer 197 EUR.\nhttps://www.amplivo.net/setup\n\nAntworte BUY – sonst ignorieren.\n\nBeste Gruesse\n{{sender_name}}\n\nP.S. STOP zum Abmelden.')
) AS v(step_order, subject_tpl, body_tpl)
WHERE s.sequence_id = es.id
  AND es.slug = 'nurture_b'
  AND s.step_order = v.step_order;

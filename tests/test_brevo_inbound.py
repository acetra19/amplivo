from packages.shared.brevo_inbound import parse_brevo_inbound


def test_parse_legacy_payload():
    parsed = parse_brevo_inbound(
        {"from_email": "Lead@Example.com", "text": "Sounds interesting", "subject": "Re: hi"},
    )
    assert parsed == {
        "from_email": "lead@example.com",
        "subject": "Re: hi",
        "text": "Sounds interesting",
    }


def test_parse_brevo_items_payload():
    parsed = parse_brevo_inbound(
        {
            "items": [
                {
                    "From": {"Address": "Alice@Example.com", "Name": "Alice"},
                    "Subject": "Yes please",
                    "RawTextBody": "I am interested",
                }
            ]
        }
    )
    assert parsed["from_email"] == "alice@example.com"
    assert parsed["subject"] == "Yes please"
    assert "interested" in parsed["text"]


def test_parse_brevo_sender_event():
    parsed = parse_brevo_inbound(
        {"sender": "bob@example.com", "subject": "Question", "text": "Tell me more"},
    )
    assert parsed["from_email"] == "bob@example.com"

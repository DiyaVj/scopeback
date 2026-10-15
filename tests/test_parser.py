from app.parser import parse_messages


def test_parse_whatsapp_export_and_multiline_message():
    raw = """12/10/26, 10:15 am - Client: Can we add a blog?
12/10/26, 10:16 am - Developer: That isn't in the quote.
It would need a separate estimate.
"""
    messages = parse_messages(raw)
    assert len(messages) == 2
    assert messages[0].id == "M001"
    assert messages[0].sender == "Client"
    assert messages[0].text == "Can we add a blog?"
    assert messages[1].text == "That isn't in the quote.\nIt would need a separate estimate."


def test_parse_pasted_transcript():
    messages = parse_messages("Client: Can we add a blog?\nDeveloper: Let me quote that separately.")
    assert [m.id for m in messages] == ["M001", "M002"]
    assert messages[0].sender == "Client"


def test_unrecognized_lines_are_preserved():
    messages = parse_messages("Client requested one more round\nNo timestamp here")
    assert len(messages) == 2
    assert "Client requested" in messages[0].text

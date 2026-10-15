from app.analyzer import Finding, ModelAnalysis, validate_and_ground
from app.parser import parse_messages


def test_grounding_rejects_invented_message_ids():
    messages = parse_messages("Client: Please add a blog.\nDeveloper: I'll estimate it separately.")
    model_result = ModelAnalysis(
        project_summary="A website project.",
        agreed_scope=["Five pages"],
        findings=[
            Finding(
                title="Blog feature",
                classification="potential_scope_change",
                summary="May be outside the quote.",
                source_message_ids=["M999"],
                scope_reference="Excluded feature",
                confidence="high",
            ),
            Finding(
                title="Separate estimate mentioned",
                classification="unclear",
                summary="The developer said they will estimate the work.",
                source_message_ids=["M002"],
                scope_reference="No clear matching clause found",
                confidence="medium",
            ),
        ],
        limitations=[],
    )
    grounded = validate_and_ground(model_result, messages)
    assert len(grounded["findings"]) == 1
    finding = grounded["findings"][0]
    assert finding["source_message_ids"] == ["M002"]
    assert finding["evidence"][0]["text"] == "I'll estimate it separately."

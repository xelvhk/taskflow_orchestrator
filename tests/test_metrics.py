from app.services.metrics import average_by_type


def test_average_by_type_groups_values() -> None:
    assert average_by_type(
        [
            ("summarize_text", 10),
            ("summarize_text", 20),
            ("video_draft", 40),
        ]
    ) == {
        "summarize_text": 15,
        "video_draft": 40,
    }

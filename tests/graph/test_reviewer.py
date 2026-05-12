from unittest.mock import MagicMock, patch

from src.graph.nodes.reviewer import reviewer_node
from src.models.state import initial_state


def test_reviewer_keeps_passing_score_when_post_check_is_clean():
    state = initial_state("他说：“你好。”", "chinese", "novel", 1)
    state["chunks"] = ["他说：“你好。”"]
    state["current_translation"] = "Anh ấy nói: “Xin chào.”"

    llm = MagicMock()
    llm.generate.return_value = '{"score": 0.9, "feedback": "Good"}'

    with (
        patch("src.graph.nodes.reviewer.get_llm", return_value=llm),
        patch("src.graph.nodes.reviewer.log_ai_call"),
    ):
        result = reviewer_node(state)

    assert result["review_score"] == 0.9
    assert result["review_feedback"] == "Good"
    assert result["post_check_issues"] == []


def test_reviewer_forces_retry_on_blocking_post_check_issue():
    state = initial_state("张三走了", "chinese", "novel", 1)
    state["chunks"] = ["张三走了"]
    state["current_translation"] = "张三走了 rồi."

    llm = MagicMock()
    llm.generate.return_value = '{"score": 0.95, "feedback": "Good"}'

    with (
        patch("src.graph.nodes.reviewer.config") as mock_config,
        patch("src.graph.nodes.reviewer.get_llm", return_value=llm),
        patch("src.graph.nodes.reviewer.log_ai_call"),
    ):
        mock_config.review_threshold = 0.7
        result = reviewer_node(state)

    assert result["review_score"] == 0.6
    assert "source-language characters" in result["review_feedback"]
    assert result["post_check_issues"] == ["contains_source_language_chars"]

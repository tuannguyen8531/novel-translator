from src.domain.illustrations import (
    detach_illustration_markers,
    restore_illustration_markers,
)


def test_detach_and_restore_illustration_markers():
    source = (
        "First paragraph.\n\n"
        "[[ILLUSTRATION:001-001.jpg]]\n\n"
        "Second paragraph.\n\n"
        "[[ILLUSTRATION:001-002.png]]"
    )

    text, placements = detach_illustration_markers(source)
    restored = restore_illustration_markers("Đoạn một.\n\nĐoạn hai.", placements)

    assert text == "First paragraph.\n\nSecond paragraph."
    assert restored == (
        "Đoạn một.\n\n"
        "[[ILLUSTRATION:001-001.jpg]]\n\n"
        "Đoạn hai.\n\n"
        "[[ILLUSTRATION:001-002.png]]"
    )


def test_restore_keeps_multiple_markers_at_same_position_in_order():
    source = (
        "Before.\n\n"
        "[[ILLUSTRATION:001-001.jpg]]\n\n"
        "[[ILLUSTRATION:001-002.jpg]]\n\n"
        "After."
    )

    _, placements = detach_illustration_markers(source)

    assert restore_illustration_markers("Trước.\n\nSau.", placements) == (
        "Trước.\n\n"
        "[[ILLUSTRATION:001-001.jpg]]\n\n"
        "[[ILLUSTRATION:001-002.jpg]]\n\n"
        "Sau."
    )

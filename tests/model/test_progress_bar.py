from paka.model.progress_bar import NullProgressBar, ProgressBar


def test_progress_bar() -> None:
    pb = ProgressBar("Testing")
    fake_pb = NullProgressBar("Testing")

    pb.create_progress_bar(100)
    fake_pb.create_progress_bar(100)
    assert pb.progress_bar.total == 100
    assert pb.progress_bar.desc == "Testing"

    pb.advance_progress_bar("task1", 10)
    fake_pb.advance_progress_bar("task1", 10)
    assert pb.progress_bar.n == 10

    pb.set_postfix_str("test postfix")
    fake_pb.set_postfix_str("test postfix")
    assert pb.progress_bar.postfix == "test postfix"

    pb.update_progress_bar("task2", 20)
    fake_pb.update_progress_bar("task2", 20)
    assert pb.progress_bar.total == 120

    pb.clear_counter()
    fake_pb.clear_counter()
    assert pb.counter == {}

    pb.close_progress_bar()
    fake_pb.close_progress_bar()
    assert pb.progress_bar is None

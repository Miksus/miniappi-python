from miniappi import App, content
import pytest

def test_run(mock_server):
    app = App()

    @app.on_start()
    async def handle_new_user():
        raise RuntimeError("Expected")

    with pytest.raises(ExceptionGroup):
        app.run()

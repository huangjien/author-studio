import os
import importlib
import pytest
import asyncio


def test_session_service_file_mode_create_and_continue(tmp_path):
    # Configure DATA_DIR for isolated file persistence
    os.environ["DATA_DIR"] = os.path.join(str(tmp_path), ".data")

    import src.config.env as env_module
    importlib.reload(env_module)
    import src.services.session_service as session_module
    importlib.reload(session_module)

    svc = session_module.session_service
    sess = svc.create_session("alpha-bot")
    assert sess.agent_id == "alpha-bot"
    # Continue same session should load from file
    continued = svc.continue_session(sess.session_id)
    assert continued is not None
    assert continued.session_id == sess.session_id

    # Unknown session returns None
    assert svc.continue_session("missing") is None


def test_session_service_sqlite_mode_init_only(tmp_path):
    # Switch to sqlite mode
    os.environ["PERSISTENCE_MODE"] = "sqlite"
    os.environ["DATA_DIR"] = os.path.join(str(tmp_path), ".data")

    import src.config.env as env_module
    importlib.reload(env_module)
    import src.services.session_service as session_module
    importlib.reload(session_module)

    svc = session_module.session_service
    # Ensure init path executes without error regardless of aiosqlite availability
    asyncio.run(svc.init())


def test_session_service_sqlite_create_and_continue(tmp_path):
    # Switch to sqlite mode to cover _persist sqlite branch and continue_session pass
    os.environ["PERSISTENCE_MODE"] = "sqlite"
    os.environ["DATA_DIR"] = os.path.join(str(tmp_path), ".data")

    import src.config.env as env_module
    import importlib
    importlib.reload(env_module)
    import src.services.session_service as session_module
    importlib.reload(session_module)

    svc = session_module.session_service
    sess = svc.create_session("gamma-bot")
    assert sess.agent_id == "gamma-bot"

    # continue_session should hit sqlite branch (pass) and return None
    assert svc.continue_session(sess.session_id) is None
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccgram.handlers.topics.directory_browser import BROWSE_PATH_KEY
from ccgram.handlers.topics.directory_callbacks import (
    _create_window_and_bind,
    _handle_confirm,
    _handle_wt_confirm,
    _handle_wt_new,
    _handle_wt_use_current,
)
from ccgram.handlers.text.text_handler import _handle_worktree_name_reply
from ccgram.handlers.user_state import (
    AWAITING_WORKTREE_BRANCH_NAME,
    PENDING_THREAD_ID,
    PENDING_WORKTREE_BRANCH,
    PENDING_WORKTREE_DIRTY,
    PENDING_WORKTREE_PATH,
    PENDING_WORKTREE_REPO,
)
from ccgram.session import SessionManager
from ccgram.window_state_store import window_store

pytestmark = pytest.mark.integration


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")
    (repo / "file.txt").write_text("hello")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    _git(repo, "branch", "-M", "main")
    return repo


@pytest.fixture
def session_manager(tmp_path, monkeypatch) -> SessionManager:
    monkeypatch.setattr("ccgram.config.config.state_file", tmp_path / "state.json")
    monkeypatch.setattr(
        "ccgram.config.config.session_map_file", tmp_path / "session_map.json"
    )
    return SessionManager()


def _make_query() -> AsyncMock:
    query = AsyncMock()
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.chat.type = "supergroup"
    query.message.chat.id = -100999
    return query


def _make_update(thread_id: int = 42) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 100
    update.message = None
    update.callback_query = MagicMock()
    update.callback_query.message = MagicMock()
    update.callback_query.message.message_thread_id = thread_id
    return update


def _make_context(user_data: dict) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data
    ctx.bot = AsyncMock()
    return ctx


@patch("ccgram.handlers.topics.directory_callbacks.safe_edit", new_callable=AsyncMock)
@patch("ccgram.handlers.topics.directory_callbacks.thread_router")
async def test_use_current_branch_skips_to_provider_picker(
    mock_tr: MagicMock, mock_edit: AsyncMock, git_repo: Path
) -> None:
    mock_tr.get_window_for_thread.return_value = None
    user_data = {BROWSE_PATH_KEY: str(git_repo), PENDING_THREAD_ID: 42}
    context = _make_context(user_data)

    await _handle_confirm(_make_query(), 100, _make_update(42), context)
    assert "Git Worktree" in mock_edit.call_args[0][1]

    await _handle_wt_use_current(_make_query(), context)
    assert "Select Provider" in mock_edit.call_args[0][1]
    assert PENDING_WORKTREE_REPO not in user_data


async def test_new_worktree_creates_and_persists_to_window_state(
    session_manager: SessionManager, git_repo: Path
) -> None:
    user_data = {
        PENDING_WORKTREE_REPO: str(git_repo),
        PENDING_WORKTREE_DIRTY: False,
    }
    context = _make_context(user_data)

    with patch(
        "ccgram.handlers.topics.directory_callbacks.safe_edit",
        new_callable=AsyncMock,
    ):
        await _handle_wt_new(_make_query(), context)
        branch = user_data[PENDING_WORKTREE_BRANCH]
        await _handle_wt_confirm(_make_query(), context)

    worktree_path = Path(user_data[PENDING_WORKTREE_PATH])
    assert worktree_path.is_dir()
    assert (worktree_path / "file.txt").exists()
    assert user_data[BROWSE_PATH_KEY] == str(worktree_path)

    mock_provider = MagicMock()
    mock_provider.capabilities.supports_hook = False
    mock_provider.capabilities.chat_first_command_path = False
    mock_provider.capabilities.has_yolo_confirmation = False

    with (
        patch("ccgram.providers.resolve_launch_command", return_value="claude"),
        patch(
            "ccgram.handlers.topics.directory_callbacks.safe_edit",
            new_callable=AsyncMock,
        ),
        patch("ccgram.handlers.topics.directory_callbacks.tmux_manager") as mock_tmux,
        patch(
            "ccgram.handlers.topics.directory_callbacks.provider_registry"
        ) as mock_registry,
        patch(
            "ccgram.handlers.topics.directory_callbacks._try_install_messaging_skill"
        ),
    ):
        mock_tmux.create_window = AsyncMock(
            return_value=(True, "Created window 'repo'", "repo", "@7")
        )
        mock_tmux.stamp_pane_title = AsyncMock()
        mock_registry.is_valid.return_value = True
        mock_registry.get.return_value = mock_provider

        await _create_window_and_bind(
            _make_query(), 100, str(worktree_path), "claude", "normal", context
        )

    state = window_store.window_states["@7"]
    assert state.worktree_path == str(worktree_path)
    assert state.worktree_branch == branch
    assert PENDING_WORKTREE_PATH not in user_data


async def test_edit_name_text_reply_revalidates_and_reconfirms(
    git_repo: Path,
) -> None:
    user_data = {
        PENDING_THREAD_ID: 42,
        PENDING_WORKTREE_REPO: str(git_repo),
        PENDING_WORKTREE_DIRTY: False,
        AWAITING_WORKTREE_BRANCH_NAME: True,
    }
    message = MagicMock()

    with patch(
        "ccgram.handlers.text.text_handler.safe_reply", new_callable=AsyncMock
    ) as mock_reply:
        handled = await _handle_worktree_name_reply(
            user_data, 42, "feature/login", message
        )

    assert handled is True
    assert user_data[PENDING_WORKTREE_BRANCH] == "feature/login"
    assert user_data[PENDING_WORKTREE_PATH].endswith("repo.worktrees/feature-login")
    assert AWAITING_WORKTREE_BRANCH_NAME not in user_data
    assert "New Worktree" in mock_reply.call_args[0][1]


async def test_edit_name_invalid_branch_reprompts(git_repo: Path) -> None:
    user_data = {
        PENDING_THREAD_ID: 42,
        PENDING_WORKTREE_REPO: str(git_repo),
        AWAITING_WORKTREE_BRANCH_NAME: True,
    }
    message = MagicMock()

    with patch(
        "ccgram.handlers.text.text_handler.safe_reply", new_callable=AsyncMock
    ) as mock_reply:
        handled = await _handle_worktree_name_reply(
            user_data, 42, "bad branch..name", message
        )

    assert handled is True
    assert user_data[AWAITING_WORKTREE_BRANCH_NAME] is True
    assert "Invalid branch name" in mock_reply.call_args[0][1]


async def test_edit_name_inactive_when_flag_unset() -> None:
    handled = await _handle_worktree_name_reply({}, 42, "x", MagicMock())
    assert handled is False


@patch("ccgram.handlers.topics.directory_callbacks.safe_edit", new_callable=AsyncMock)
@patch("ccgram.handlers.topics.directory_callbacks.thread_router")
async def test_non_git_directory_skips_worktree_picker(
    mock_tr: MagicMock, mock_edit: AsyncMock, tmp_path: Path
) -> None:
    mock_tr.get_window_for_thread.return_value = None
    plain = tmp_path / "plain"
    plain.mkdir()
    user_data = {BROWSE_PATH_KEY: str(plain), PENDING_THREAD_ID: 42}
    context = _make_context(user_data)

    await _handle_confirm(_make_query(), 100, _make_update(42), context)

    assert "Select Provider" in mock_edit.call_args[0][1]
    assert PENDING_WORKTREE_REPO not in user_data

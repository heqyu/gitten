import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_main_uses_cwd_when_no_arg(tmp_path, monkeypatch):
    """main() passes cwd to app when no path argument given."""
    monkeypatch.chdir(tmp_path)
    import git
    git.Repo.init(tmp_path)

    with patch("gitten.main.GittenApp") as mock_app_cls:
        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app
        with patch("sys.argv", ["gitten"]):
            from gitten.main import main
            main()
        mock_app_cls.assert_called_once_with(repo_path=tmp_path)
        mock_app.run.assert_called_once()


def test_main_accepts_path_argument(tmp_path):
    """main() passes provided path to app."""
    import git
    git.Repo.init(tmp_path)

    with patch("gitten.main.GittenApp") as mock_app_cls:
        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app
        with patch("sys.argv", ["gitten", str(tmp_path)]):
            from gitten.main import main
            main()
        mock_app_cls.assert_called_once_with(repo_path=tmp_path)


def test_main_exits_on_invalid_repo(tmp_path, capsys):
    """main() prints error and exits when path is not a git repo."""
    with patch("sys.argv", ["gitten", str(tmp_path)]):
        from gitten.main import main
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "not a git repository" in captured.err.lower()

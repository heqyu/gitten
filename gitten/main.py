import sys
from pathlib import Path

try:
    from gitten.app import GittенApp
except ImportError:
    GittенApp = None  # type: ignore[assignment,misc]


def main() -> None:
    args = sys.argv[1:]
    repo_path = Path(args[0]) if args else Path.cwd()

    # Validate git repo
    try:
        import git
        git.Repo(repo_path)
    except git.InvalidGitRepositoryError:
        print(f"Error: {repo_path} is not a git repository.", file=sys.stderr)
        sys.exit(1)
    except git.NoSuchPathError:
        print(f"Error: path {repo_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    app = GittенApp(repo_path=repo_path)
    app.run()


if __name__ == "__main__":
    main()

"""Guard the migration chain.

CI runs ruff, black and pytest — none of which touch a database — so a forked revision
chain used to reach `dev` completely green and only fail for whoever set up next.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]


def script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))


def test_there_is_exactly_one_head():
    """Two branches each adding a migration off the same parent forks the chain.

    When that happens `alembic upgrade head` refuses to run. The fix is a merge
    revision whose down_revision is a tuple of both heads — see 0004_merge_heads.
    """
    heads = script_directory().get_heads()
    assert len(heads) == 1, (
        f"{len(heads)} alembic heads: {sorted(heads)}. Two migrations share a parent, so "
        "`alembic upgrade head` will fail. Add a merge revision: "
        "`alembic merge -m 'merge heads' " + " ".join(sorted(heads)) + "`"
    )


def test_every_revision_is_reachable_from_the_base():
    """No orphan revision: walking down from the head reaches 0001_initial."""
    script = script_directory()
    (head,) = script.get_heads()
    walked = {rev.revision for rev in script.walk_revisions("base", head)}
    on_disk = {rev.revision for rev in script.walk_revisions()}
    assert walked == on_disk, f"unreachable revisions: {sorted(on_disk - walked)}"

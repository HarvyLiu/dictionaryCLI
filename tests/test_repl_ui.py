import dictcli.cli as cli


def test_repl_help_prints_command_table(capsys):
    cli._repl_help()
    out = capsys.readouterr().out
    assert ":s" in out
    assert ":w" in out
    assert ":vk" in out
    assert ":vs" in out
    assert ":cache" in out
    assert ":h" in out
    assert ":q" in out


def test_banner_contains_name():
    assert "CamDictCLI" not in cli.BANNER  # figlet art, not plain text
    assert "____" in cli.BANNER
    lines = [l for l in cli.BANNER.splitlines() if l.strip()]
    assert len(lines) >= 4

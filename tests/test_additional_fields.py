from markdown_generator import MarkdownGenerator


class FakeOption:
    def __init__(self, value):
        self.value = value


class FakeNamed:
    def __init__(self, name):
        self.name = name


class FakeUser:
    def __init__(self, display_name):
        self.displayName = display_name


class FakeFields:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeIssue:
    def __init__(self, **fields):
        self.fields = FakeFields(**fields)
        self.key = "TEST-1"
        self.id = "1"


def make_generator(issue, field_names=None):
    return MarkdownGenerator(issue, field_names=field_names or {})


def test_is_empty_description():
    assert MarkdownGenerator._is_empty_description(None) is True
    assert MarkdownGenerator._is_empty_description("") is True
    assert MarkdownGenerator._is_empty_description("\n\n") is True
    assert MarkdownGenerator._is_empty_description("   ") is True
    assert MarkdownGenerator._is_empty_description("real text") is False


def test_format_prose_string_converts():
    issue = FakeIssue(description=None)
    gen = make_generator(issue)
    out = gen._format_additional_value("h3. Risk\n\nSome risk text")
    assert "Risk" in out
    assert "Some risk text" in out


def test_format_empty_string_returns_none():
    issue = FakeIssue(description=None)
    gen = make_generator(issue)
    assert gen._format_additional_value("   ") is None
    assert gen._format_additional_value("\n\n") is None
    assert gen._format_additional_value("{}") is None
    assert gen._format_additional_value("[]") is None


def test_format_single_option_returns_value():
    issue = FakeIssue(description=None)
    gen = make_generator(issue)
    assert gen._format_additional_value(FakeOption("Synthetic")) == "Synthetic"


def test_format_option_list_joins_values():
    issue = FakeIssue(description=None)
    gen = make_generator(issue)
    out = gen._format_additional_value([FakeOption("A"), FakeOption("B")])
    assert out == "A, B"


def test_format_user_uses_display_name():
    issue = FakeIssue(description=None)
    gen = make_generator(issue)
    assert gen._format_additional_value(FakeUser("Alice Example")) == "Alice Example"


def test_format_user_list_joins_display_names():
    issue = FakeIssue(description=None)
    gen = make_generator(issue)
    out = gen._format_additional_value([FakeUser("Alice"), FakeUser("Bob")])
    assert out == "Alice, Bob"


def test_generate_additional_fields_renders_populated_unmapped():
    field_names = {
        "customfield_22091": "User pain point",
        "customfield_20795": "Product Area",
        "customfield_99999": "Empty Field",
        "description": "Description",  # mapped -- must be excluded
    }
    issue = FakeIssue(
        description=None,
        customfield_22091="Users cannot select a CAG in the UI.",
        customfield_20795=FakeOption("Synthetic"),
        customfield_99999=None,
    )
    gen = make_generator(issue, field_names)
    out = gen._generate_additional_fields(issue)
    assert out.startswith("## Details")
    assert "### Product Area" in out
    assert "Synthetic" in out
    assert "### User pain point" in out
    assert "Users cannot select a CAG in the UI." in out
    assert "Empty Field" not in out


def test_generate_additional_fields_excludes_mapped_fields():
    field_names = {
        "customfield_17800": "Team",
        "description": "Description",
    }
    issue = FakeIssue(description=None, customfield_17800=FakeOption("Synthetic Team"))
    gen = make_generator(issue, field_names)
    assert gen._generate_additional_fields(issue) is None


def test_generate_additional_fields_returns_none_when_nothing():
    issue = FakeIssue(description=None, customfield_22091=None)
    gen = make_generator(issue, {"customfield_22091": "User pain point"})
    assert gen._generate_additional_fields(issue) is None


def test_generate_markdown_uses_details_when_description_empty(monkeypatch):
    field_names = {"customfield_22091": "User pain point"}
    issue = FakeIssue(
        summary="S",
        description="",
        customfield_22091="Real pain content",
        issuetype=None,
        status=None,
        assignee=None,
        parent=None,
    )
    gen = make_generator(issue, field_names)
    md = gen.generate_markdown("2026-01-01 00-00-00")
    assert "## Details" in md
    assert "### User pain point" in md
    assert "Real pain content" in md
    assert "## Description" not in md


def test_generate_markdown_uses_description_when_present():
    field_names = {"customfield_22091": "User pain point"}
    issue = FakeIssue(
        summary="S",
        description="A real description.",
        customfield_22091="Should not appear",
        issuetype=None,
        status=None,
        assignee=None,
        parent=None,
    )
    gen = make_generator(issue, field_names)
    md = gen.generate_markdown("2026-01-01 00-00-00")
    assert "## Description" in md
    assert "A real description." in md
    assert "## Details" not in md
    assert "Should not appear" not in md


def test_release_notes_section_includes_new_fields():
    issue = FakeIssue(
        summary="S",
        description="d",
        issuetype=None,
        status=None,
        assignee=None,
        parent=None,
        customfield_15900=[FakeOption("Yes")],
        customfield_22157=FakeOption("New technology support"),
        customfield_20300="Managed (344), SaaS (344)",
        customfield_19502=FakeOption("Application Observability"),
        customfield_19701="Some Release Notes Title",
        customfield_15000="Some release notes summary text.",
    )
    gen = make_generator(issue)
    md = gen.generate_markdown("2026-01-01 00-00-00")
    assert "## Release Notes" in md
    assert "**Relevant for release notes:** Yes" in md
    assert "**Change type:** New technology support" in md
    assert "**Release versions:** Managed (344), SaaS (344)" in md
    assert "**Category:** Application Observability" in md
    assert "**Title:** Some Release Notes Title" in md
    assert "Some release notes summary text." in md


def test_release_notes_section_absent_when_all_empty():
    issue = FakeIssue(
        summary="S",
        description="d",
        issuetype=None,
        status=None,
        assignee=None,
        parent=None,
    )
    gen = make_generator(issue)
    md = gen.generate_markdown("2026-01-01 00-00-00")
    assert "## Release Notes" not in md

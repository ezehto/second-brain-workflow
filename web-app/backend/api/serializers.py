"""Request and response serializers: the shapes of the API contract (plan section 5).

Nullable fields are `null`, never missing. Status vocabularies come from
`vault.conventions`. The views are stubs until their tasks land; these classes are what the
OpenAPI document is generated from.
"""

from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination

from vault.conventions import (
    ALL_STATUSES,
    CLASSIFICATION_ACTIONS,
    CLASSIFICATIONS,
    CREATABLE_TYPES,
    PRIORITIES,
    STANDUP_HEADINGS,
    STATUSES,
    TARGET_ACTIONS,
    TRIAGE_ACTIONS,
)
from vault.dates import frontmatter_date

INDEX_PROBLEM_CATEGORIES = (
    "parse_errors",
    "missing_ids",
    "duplicate_ids",
    "ambiguous_links",
    "unknown_project_slugs",
    "duplicate_project_slugs",
    "unknown_statuses",
    "invalid_dates",
)
NOTE_ORDERINGS = ("-modified", "due", "title", "path", "-path")


HASH_PATTERN = r"^[0-9a-f]{64}$"
PATH_MAX = 200
TEXT_MAX = 255


def expected_hash_field(**kwargs) -> serializers.RegexField:
    """A SHA-256 hex digest, as `content_hash` reports it."""
    return serializers.RegexField(HASH_PATTERN, **kwargs)


def frontmatter_text(value) -> str | None:
    """A scalar frontmatter value as text; None for null, blank, lists and mappings."""
    if value is None or isinstance(value, list | dict):
        return None
    text = ("true" if value else "false") if isinstance(value, bool) else str(value)
    return text.strip() or None


class NotePagination(PageNumberPagination):
    """Page-number pagination: `page` and `page_size` (default 50, at most 200)."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_schema_operation_parameters(self, view):
        parameters = super().get_schema_operation_parameters(view)
        for parameter in parameters:
            if parameter["name"] == self.page_size_query_param:
                parameter["schema"].update(minimum=1, maximum=self.max_page_size)
        return parameters


# --- errors ---------------------------------------------------------------------------------


class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()


class AmbiguousLookupErrorSerializer(ErrorSerializer):
    candidates = serializers.ListField(
        child=serializers.CharField(), help_text="Paths of the notes a `?id=` lookup matched."
    )


class PartialTriageErrorSerializer(ErrorSerializer):
    created_target = serializers.CharField(
        required=False,
        help_text=(
            "Path of the target note a triage created before the capture edit failed. "
            "Retry with it as `existing_target`."
        ),
    )


# --- health and auth ------------------------------------------------------------------------


class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "error"])


class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    # Whitespace is part of a password, so it is not trimmed before the check.
    password = serializers.CharField(
        max_length=4096, trim_whitespace=False, style={"input_type": "password"}
    )


class MeSerializer(serializers.Serializer):
    username = serializers.CharField()


# --- notes ----------------------------------------------------------------------------------


class NoteSummarySerializer(serializers.Serializer):
    """Promoted fields of one indexed note."""

    id = serializers.CharField(
        source="note_id",
        allow_null=True,
        help_text="The `id` frontmatter value; null for a note without one.",
    )
    path = serializers.CharField(help_text="Vault-relative path.")
    type = serializers.CharField(help_text="A known type, `note`, or an unknown type as written.")
    title = serializers.CharField()
    status = serializers.CharField(
        allow_null=True, help_text="Stored as written, even outside the type's vocabulary."
    )
    priority = serializers.CharField(
        allow_null=True, help_text="Stored as written; one of low/medium/high when valid."
    )
    project = serializers.CharField(allow_null=True, help_text="Project slug as written.")
    due = serializers.DateField(allow_null=True, help_text="Null when absent or unreadable.")
    blocked_by = serializers.CharField(allow_null=True)
    decided = serializers.DateField(
        allow_null=True, help_text="Decisions: set when the status became accepted."
    )
    tags = serializers.ListField(child=serializers.CharField(), source="tags.all")
    created = serializers.DateField(allow_null=True)
    modified = serializers.DateTimeField(
        source="file_mtime", help_text="Local time with the vault's offset."
    )
    parse_error = serializers.CharField(allow_null=True)

    def to_representation(self, instance):
        """`blocked_by` and `decided` have no column: they are read from the frontmatter."""
        data = super().to_representation(instance)
        frontmatter = instance.frontmatter
        data["blocked_by"] = frontmatter_text(frontmatter.get("blocked_by"))
        decided = frontmatter_date(frontmatter.get("decided"))
        data["decided"] = decided.isoformat() if decided else None
        return data


class BacklinkSerializer(serializers.Serializer):
    path = serializers.CharField()
    title = serializers.CharField()


class ResolvedLinkSerializer(serializers.Serializer):
    path = serializers.CharField(allow_null=True)
    state = serializers.ChoiceField(choices=["resolved", "ambiguous", "unresolved"])


class NoteDetailSerializer(NoteSummarySerializer):
    """One note in full."""

    frontmatter = serializers.DictField(help_text="The parsed frontmatter mapping.")
    body = serializers.CharField(allow_blank=True)
    content_hash = serializers.CharField(help_text="Send back as `expected_hash` when writing.")
    backlinks = BacklinkSerializer(many=True, help_text="Notes that link here.")
    links = serializers.DictField(
        source="resolved_links",
        child=ResolvedLinkSerializer(),
        help_text="Each link target as written in the body, mapped to where it resolves.",
    )


class NoteListQuerySerializer(serializers.Serializer):
    """Query parameters of `GET /api/notes/` (`page` and `page_size` come from pagination)."""

    type = serializers.CharField(required=False, max_length=TEXT_MAX)
    status = serializers.ListField(
        child=serializers.CharField(), required=False, help_text="Repeatable."
    )
    priority = serializers.ChoiceField(choices=PRIORITIES, required=False)
    project = serializers.CharField(required=False, max_length=PATH_MAX, help_text="Project slug.")
    tag = serializers.CharField(required=False, max_length=TEXT_MAX)
    due_before = serializers.DateField(required=False)
    due_after = serializers.DateField(required=False)
    overdue = serializers.BooleanField(required=False)
    path_prefix = serializers.CharField(required=False, max_length=PATH_MAX)
    has_parse_error = serializers.BooleanField(required=False)
    ordering = serializers.ChoiceField(
        choices=NOTE_ORDERINGS,
        required=False,
        help_text="Default `-modified`. Every ordering ends with `path`.",
    )


class NoteLookupQuerySerializer(serializers.Serializer):
    path = serializers.CharField(
        required=False, max_length=PATH_MAX, help_text="Vault-relative path."
    )
    id = serializers.CharField(
        required=False, max_length=TEXT_MAX, help_text="The `id` frontmatter value."
    )


class CreateNoteRequestSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=CREATABLE_TYPES)
    title = serializers.CharField(max_length=PATH_MAX)
    project = serializers.CharField(
        required=False, max_length=PATH_MAX, help_text="Project slug or title."
    )
    priority = serializers.ChoiceField(choices=PRIORITIES, required=False)
    due = serializers.DateField(required=False)
    status = serializers.ChoiceField(
        choices=ALL_STATUSES,
        required=False,
        help_text="From the vocabulary of `type` (plan section 2.3); default per type.",
    )
    body = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        status = attrs.get("status")
        if status is not None and status not in STATUSES[attrs["type"]]:
            raise serializers.ValidationError(
                {"status": f"Not a status of a {attrs['type']} note."}
            )
        return attrs


class StatusChangeRequestSerializer(serializers.Serializer):
    path = serializers.CharField(max_length=PATH_MAX)
    status = serializers.ChoiceField(
        choices=ALL_STATUSES,
        help_text="Must belong to the vocabulary of the note's type; checked against the note.",
    )
    expected_hash = expected_hash_field()
    evidence = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Appended under `## Notes` when the status becomes `done`.",
    )


# --- captures -------------------------------------------------------------------------------


class CaptureRequestSerializer(serializers.Serializer):
    text = serializers.CharField()


class TriageRequestSerializer(serializers.Serializer):
    path = serializers.CharField(max_length=PATH_MAX)
    expected_hash = expected_hash_field(
        help_text="Checked before a target note is created, not only before the capture edit."
    )
    action = serializers.ChoiceField(choices=TRIAGE_ACTIONS)
    classification = serializers.ChoiceField(
        choices=CLASSIFICATIONS,
        required=False,
        help_text=(
            "Required for every action but `dismiss`. An action that creates a target needs a "
            "classification that files as that action (`task`/`problem` for `task`, `decision`, "
            "`learning-topic`/`note` for `lesson`, `project`); `keep` and `dismiss` take any."
        ),
    )
    title = serializers.CharField(required=False, max_length=PATH_MAX)
    project = serializers.CharField(required=False, max_length=PATH_MAX)
    existing_target = serializers.CharField(
        required=False,
        max_length=PATH_MAX,
        help_text=(
            "Retry after a partial failure: a vault-relative `.md` path of the target already "
            "created. Skips creation and only edits the capture."
        ),
    )

    def validate(self, attrs):
        action, classification = attrs["action"], attrs.get("classification")
        if action != "dismiss" and classification is None:
            raise serializers.ValidationError(
                {"classification": "Required unless the action is dismiss."}
            )
        if action in TARGET_ACTIONS and CLASSIFICATION_ACTIONS.get(classification) != action:
            filed_as = CLASSIFICATION_ACTIONS.get(classification)
            raise serializers.ValidationError(
                {
                    "classification": (
                        f"{classification!r} "
                        + (f"files as action {filed_as!r}" if filed_as else "creates no target")
                        + f", not {action!r} (plan 2.13). Use `keep` or the matching action."
                    )
                }
            )
        return attrs


class TriageResponseSerializer(serializers.Serializer):
    capture = NoteDetailSerializer()
    target = NoteSummarySerializer(
        allow_null=True, help_text="The note created or reused; null for `keep` and `dismiss`."
    )


# --- projects -------------------------------------------------------------------------------


class ProjectSummarySerializer(serializers.Serializer):
    slug = serializers.CharField()
    title = serializers.CharField()
    path = serializers.CharField()
    status = serializers.CharField(allow_null=True)
    goal = serializers.CharField(allow_null=True)
    open_task_count = serializers.IntegerField(min_value=0)
    modified = serializers.DateTimeField()


class ProjectDetailSerializer(serializers.Serializer):
    project = ProjectSummarySerializer()
    note = NoteDetailSerializer()
    open_tasks = NoteSummarySerializer(many=True)
    decisions = NoteSummarySerializer(many=True)
    recent_notes = NoteSummarySerializer(many=True, help_text="By modified time, then path.")


# --- standups -------------------------------------------------------------------------------

# One field per standup heading. The names contain spaces and slashes, so the class is built
# from the heading list rather than written out.
StandupPreviewSerializer = type(
    "StandupPreview",
    (serializers.Serializer,),
    {
        section: serializers.ListField(child=serializers.CharField(allow_blank=True))
        for section in STANDUP_HEADINGS
    },
)
StandupPreviewSerializer.__doc__ = "The six standup sections as lines of Markdown."


@extend_schema_field({"type": "boolean", "enum": [True]})
class AlwaysTrueField(serializers.BooleanField):
    pass


@extend_schema_field({"type": "boolean", "enum": [False]})
class AlwaysFalseField(serializers.BooleanField):
    pass


class StandupExistingSerializer(serializers.Serializer):
    """Today's daily note exists."""

    exists = AlwaysTrueField()
    note = NoteDetailSerializer()
    untouched = serializers.BooleanField()


class StandupMissingSerializer(serializers.Serializer):
    """Today's daily note does not exist: what starting the standup would write."""

    exists = AlwaysFalseField()
    preview = StandupPreviewSerializer()


class StartStandupResponseSerializer(serializers.Serializer):
    created = serializers.BooleanField(help_text="True on 201: a new note with carry-forward.")
    filled = serializers.BooleanField(
        help_text="An untouched note was filled (true) or a touched one returned unchanged."
    )
    note = NoteDetailSerializer()
    untouched = serializers.BooleanField()


class AppendStandupResponseSerializer(serializers.Serializer):
    note = NoteDetailSerializer()
    section_created = serializers.BooleanField(
        help_text="True when the heading was missing and was added to the note (2.4 rule 6)."
    )


class AppendStandupRequestSerializer(serializers.Serializer):
    section = serializers.ChoiceField(choices=STANDUP_HEADINGS)
    text = serializers.CharField(
        help_text="The bare line: the writer adds the list marker for the section."
    )
    expected_hash = expected_hash_field()


# --- dashboard ------------------------------------------------------------------------------


class IndexSummarySerializer(serializers.Serializer):
    last_pass_at = serializers.DateTimeField(allow_null=True)
    problem_count = serializers.IntegerField(min_value=0)


@extend_schema_field(
    PolymorphicProxySerializer(
        component_name="StandupToday",
        serializers=[StandupExistingSerializer, StandupMissingSerializer],
        resource_type_field_name=None,
    )
)
class StandupTodayField(serializers.DictField):
    """Today's standup: the existing note (`exists: true`) or the preview (`exists: false`)."""


class DashboardSerializer(serializers.Serializer):
    today = serializers.DateField(help_text="The vault's today (honours the test clock).")
    today_tasks = NoteSummarySerializer(many=True)
    in_progress = NoteSummarySerializer(many=True)
    blocked = NoteSummarySerializer(many=True)
    overdue = NoteSummarySerializer(many=True)
    standup = StandupTodayField()
    recent_activity = NoteSummarySerializer(many=True)
    active_projects = ProjectSummarySerializer(many=True)
    inbox_count = serializers.IntegerField(min_value=0)
    index = IndexSummarySerializer()


# --- search ---------------------------------------------------------------------------------


class SearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(max_length=500, help_text="Search text.")


class SearchResultSerializer(serializers.Serializer):
    path = serializers.CharField()
    type = serializers.CharField()
    title = serializers.CharField()
    project = serializers.CharField(allow_null=True, help_text="The note's project slug.")
    snippet = serializers.CharField(allow_blank=True, help_text="Plain text, never HTML.")
    source = serializers.ChoiceField(choices=["vault"])


class SearchResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    results = SearchResultSerializer(many=True)


# --- index ----------------------------------------------------------------------------------


class IndexProblemSerializer(serializers.Serializer):
    path = serializers.CharField()
    detail = serializers.CharField()


IndexProblemsSerializer = type(
    "IndexProblems",
    (serializers.Serializer,),
    {name: IndexProblemSerializer(many=True) for name in INDEX_PROBLEM_CATEGORIES},
)


class PinnedDateSerializer(serializers.Serializer):
    today = serializers.DateField(help_text="The pinned date.")


class IndexStatusSerializer(serializers.Serializer):
    last_pass_at = serializers.DateTimeField(allow_null=True)
    duration_ms = serializers.IntegerField(allow_null=True, min_value=0)
    counts_by_type = serializers.DictField(child=serializers.IntegerField(min_value=0))
    problems = IndexProblemsSerializer()
    test_mode = PinnedDateSerializer(
        allow_null=True, help_text="Set only when plan section 2.12 test mode is on."
    )


class RefreshSummarySerializer(serializers.Serializer):
    """The summary of one sync pass (the indexer's `PassSummary`)."""

    duration_ms = serializers.IntegerField(
        min_value=0, help_text="The indexer's `duration_s`, converted to milliseconds."
    )
    scanned = serializers.IntegerField()
    read = serializers.IntegerField()
    added = serializers.IntegerField()
    changed = serializers.IntegerField()
    removed = serializers.IntegerField()
    moved = serializers.IntegerField()
    over_budget = serializers.BooleanField()
    index_parse_errors = serializers.IntegerField(help_text="Index-wide total after the pass.")
    index_duplicate_ids = serializers.IntegerField(help_text="Index-wide total after the pass.")
    index_missing_ids = serializers.IntegerField(help_text="Index-wide total after the pass.")

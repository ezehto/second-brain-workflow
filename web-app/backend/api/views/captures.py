"""Captures: quick capture and triage (P1-28)."""

from pathlib import Path

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import (
    CaptureRequestSerializer,
    ErrorSerializer,
    NoteSummarySerializer,
    PartialTriageErrorSerializer,
    TriageRequestSerializer,
    TriageResponseSerializer,
)
from api.views import writes
from api.views.common import validation_detail
from vault.conventions import TARGET_ACTIONS
from vault.ignore import iter_note_paths
from vault.writer import ConflictError, ValidationError, VaultWriter

# The note type each target-creating action writes (2.13): the action names the type.
TARGET_TYPES = {action: action for action in TARGET_ACTIONS}


def _first_line(text: str) -> str | None:
    return next((line.strip() for line in text.splitlines() if line.strip()), None)


def _wikilink(root: Path, path: str) -> str:
    """`[[Name]]` when no other note on disk shares the name, else `[[folder/Name]]` (links.md).

    The names come from the vault tree, not the index, which may lag an Obsidian edit.
    """
    target = path.removesuffix(".md")
    stem = target.rpartition("/")[2]
    same = [
        other
        for other in iter_note_paths(root)
        if other.removesuffix(".md").rpartition("/")[2].casefold() == stem.casefold()
    ]
    return f"[[{stem if len(same) <= 1 else target}]]"


class CaptureView(APIView):
    @extend_schema(
        operation_id="captures_create",
        tags=["captures"],
        summary="Quick capture",
        description="Creates a `capture` note from `text`.",
        request=CaptureRequestSerializer,
        responses={
            201: NoteSummarySerializer,
            400: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        form = CaptureRequestSerializer(data=request.data)
        if not form.is_valid():
            return Response(validation_detail(form.errors), status=status.HTTP_400_BAD_REQUEST)
        text = form.validated_data["text"]

        def capture(writer: VaultWriter) -> Response:
            created = writer.create("capture", body=text)
            note = writes.index(writer.root, created.path)
            return Response(writes.summary_data(note), status=status.HTTP_201_CREATED)

        return writes.run_write(capture)


class TriageView(APIView):
    @extend_schema(
        operation_id="captures_triage",
        tags=["captures"],
        summary="Triage a capture",
        description=(
            "Checks `expected_hash` first, then writes the target note, then edits the capture. "
            "If the capture edit fails, the `409` or `422` body carries `created_target`; retry "
            "with `existing_target` set to that path, which skips creation, passes the path "
            "through the writer's path confinement (`400` when it fails) and checks the target "
            "exists before editing the capture. `classification` is required unless the action "
            "is `dismiss`."
        ),
        request=TriageRequestSerializer,
        responses={
            200: TriageResponseSerializer,
            400: ErrorSerializer,
            404: ErrorSerializer,
            409: PartialTriageErrorSerializer,
            422: PartialTriageErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        form = TriageRequestSerializer(data=request.data)
        if not form.is_valid():
            return Response(validation_detail(form.errors), status=status.HTTP_400_BAD_REQUEST)
        fields = form.validated_data
        return writes.run_write(lambda writer: self._triage(writer, fields))

    def _triage(self, writer: VaultWriter, fields: dict) -> Response:
        root, action = writer.root, fields["action"]
        # Both paths are confined (nothing read) before the capture is read or indexed.
        existing_rel = None
        if action in TARGET_TYPES and "existing_target" in fields:
            existing_rel = writes.locate(writer, fields["existing_target"])
        capture_rel = writes.locate(writer, fields["path"])
        capture = writes.index(root, capture_rel)
        if capture.content_hash != fields["expected_hash"].strip().lower():
            raise ConflictError(f"{capture_rel!r} changed since it was read")
        if capture.type != "capture":
            raise ValidationError(f"{capture_rel!r} is not a capture")
        if capture.status != "inbox":
            raise ValidationError(f"{capture_rel!r} is already {capture.status}, not inbox")

        made_path = None  # set the moment the target exists: every later failure reports it
        if action in TARGET_TYPES and existing_rel is None:
            made_path = writer.create(
                TARGET_TYPES[action],
                fields.get("title") or _first_line(capture.body),
                project=fields.get("project"),
            ).path
        try:
            target = None
            if action in TARGET_TYPES:
                target = writes.index(root, existing_rel or made_path)
                if existing_rel and target.path == capture_rel:
                    raise ValidationError("the capture cannot be its own target")
                if existing_rel and target.type != TARGET_TYPES[action]:
                    raise ValidationError(
                        f"{target.path!r} is a {target.type} note, not a {TARGET_TYPES[action]}"
                    )
                changes = {
                    "status": "triaged",
                    "classification": fields["classification"],
                    "triaged_to": _wikilink(root, target.path),
                }
            elif action == "keep":
                changes = {"classification": fields["classification"]}
            else:  # dismiss
                changes = {"status": "dismissed"}
                if "classification" in fields:
                    changes["classification"] = fields["classification"]
            writer.set_frontmatter(capture_rel, changes, expected_hash=fields["expected_hash"])
            return Response(
                {
                    "capture": writes.detail_data(writes.index(root, capture_rel)),
                    "target": writes.summary_data(target) if target else None,
                }
            )
        except Exception as exc:
            if made_path is None:
                raise
            # The target exists: report it so the caller can retry with `existing_target`.
            return writes.failure(exc, created_target=made_path)

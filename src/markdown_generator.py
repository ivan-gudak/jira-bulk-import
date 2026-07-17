"""
Markdown generation module.
Converts Jira issue data to markdown format.
"""

from typing import Any, List
from config import FIELD_MAPPING, EXPORT_FIELDS, JIRA_BASE_URL
from jira_markup_converter import JiraMarkupConverter
from field_formatter import FieldFormatter
from attachment_handler import AttachmentHandler


class MarkdownGenerator:
    """Generates markdown from Jira issue data."""

    def __init__(self, issue: Any, jira_client: Any = None,
                 attachments_dir: str = None, shared_dir: str = None,
                 field_names: dict | None = None):
        self.issue = issue
        self.fields = issue.fields
        self.converter = JiraMarkupConverter(JIRA_BASE_URL)
        self.formatter = FieldFormatter()
        self.attachment_handler = None
        self.field_names = field_names or {}

        if jira_client and attachments_dir:
            self.attachment_handler = AttachmentHandler(
                jira_client, attachments_dir, shared_dir=shared_dir
            )

    @staticmethod
    def _is_empty_description(description: Any) -> bool:
        """True when description is None, empty, or whitespace-only."""
        return not description or not str(description).strip()

    def _format_additional_value(self, value: Any) -> str | None:
        """Format one custom-field value for the Details section. Returns None if empty."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped in ("{}", "[]"):
                return None
            converted = self.converter.convert(value)
            if self.attachment_handler is not None:
                converted = self.attachment_handler.replace_attachment_references(converted)
            return converted.strip() or None
        if isinstance(value, list):
            parts = []
            for item in value:
                if hasattr(item, 'displayName'):
                    parts.append(item.displayName)
                else:
                    parts.append(self.formatter.format_custom_field(item))
            parts = [p for p in parts if p]
            return ', '.join(parts) if parts else None
        if hasattr(value, 'displayName'):
            return value.displayName
        return self.formatter.format_custom_field(value)

    def _generate_additional_fields(self, issue: Any) -> str | None:
        """Render populated custom fields not already shown elsewhere, as a Details section.

        Used as a fallback when the standard description is empty/missing (e.g. RFE tickets
        that carry their content in custom fields instead of the description field).
        """
        excluded = set(FIELD_MAPPING.values())
        lines = []
        for field_id, display_name in sorted(self.field_names.items(), key=lambda kv: kv[1]):
            if not field_id.startswith('customfield_'):
                continue
            if field_id in excluded:
                continue
            value = getattr(issue.fields, field_id, None)
            if value is None:
                continue
            formatted = self._format_additional_value(value)
            if not formatted:
                continue
            lines.append(f"### {display_name}")
            lines.append("")
            lines.append(formatted)
            lines.append("")
        if not lines:
            return None
        return "## Details\n\n" + "\n".join(lines).rstrip()

    def generate_frontmatter(self) -> str:
        lines = ["---"]
        for field_name in EXPORT_FIELDS:
            field_id = FIELD_MAPPING.get(field_name)
            if not field_id:
                continue
            value = self._extract_field_value(field_id)
            if value is not None:
                yaml_key = field_name.lower().replace(" ", "_")
                lines.append(f"{yaml_key}: {self._format_yaml_value(value)}")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    def _extract_field_value(self, field_id: str) -> Any:
        if field_id == "key":
            return self.issue.key
        try:
            value = getattr(self.fields, field_id, None)
            if field_id == "parent":
                return self.formatter.format_parent(value)
            elif field_id in ("issuelinks", "customfield_19701", "customfield_15000", "customfield_19200"):
                return None
            elif field_id in ("assignee", "reporter", "customfield_21107", "customfield_19400"):
                return self.formatter.format_user(value)
            elif field_id in ("fixVersions", "labels"):
                return self.formatter.format_array(value)
            elif field_id in ("issuetype", "status", "project", "resolution"):
                return value.name if value and hasattr(value, "name") else None
            elif field_id.startswith("customfield_"):
                return self.formatter.format_custom_field(value)
            return value
        except AttributeError:
            return None

    def _format_yaml_value(self, value: Any) -> str:
        if value is None:
            return '""'
        if isinstance(value, str):
            return f'"{value.replace(chr(34), chr(92)+chr(34)).replace(chr(10), " ")}"'
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, list):
            if not value:
                return "[]"
            items = [f'"{i}"' if isinstance(i, str) else str(i) for i in value]
            return f"[{', '.join(items)}]"
        return f'"{str(value).replace(chr(34), chr(92)+chr(34)).replace(chr(10), " ")}"'

    def generate_markdown(self, timestamp: str) -> str:
        lines = []

        images, others = [], []
        if self.attachment_handler:
            print("  Downloading attachments...")
            images, others = self.attachment_handler.download_attachments(self.issue)

        lines.append(self.generate_frontmatter())

        summary = getattr(self.fields, "summary", "Untitled")
        lines.append(f"# {self.issue.key}: {summary}")
        lines.append("")

        lines.append("## Metadata")
        lines.append("")
        lines.append(f"**Jira Link:** {self.formatter.format_issue_link(self.issue.key)}")

        issue_type = getattr(self.fields, "issuetype", None)
        if issue_type and hasattr(issue_type, "name"):
            lines.append(f"**Type:** {issue_type.name}")

        status = getattr(self.fields, "status", None)
        if status and hasattr(status, "name"):
            lines.append(f"**Status:** {status.name}")

        assignee = self.formatter.format_user(getattr(self.fields, "assignee", None))
        if assignee:
            lines.append(f"**Assignee:** {assignee}")
        lines.append("")

        parent = getattr(self.fields, "parent", None)
        if parent:
            parent_formatted = self.formatter.format_parent_link(parent)
            if parent_formatted:
                lines.append(f"**Parent:** {parent_formatted}")
                lines.append("")

        status_details = getattr(self.fields, "customfield_19200", None)
        if status_details:
            lines.append("## Status Details")
            lines.append("")
            lines.append(self.converter.convert(status_details))
            lines.append("")

        description = getattr(self.fields, "description", None)
        if not self._is_empty_description(description):
            lines.append("## Description")
            lines.append("")
            converted = self.converter.convert(description)
            if self.attachment_handler:
                converted = self.attachment_handler.replace_attachment_references(converted)
            lines.append(converted)
            lines.append("")
        else:
            details = self._generate_additional_fields(self.issue)
            if details:
                lines.append(details)
                lines.append("")

        if self.attachment_handler and (images or others):
            lines.append(self.attachment_handler.get_attachment_list_markdown(images, others))

        release_relevant = getattr(self.fields, "customfield_15900", None)
        release_change_type = getattr(self.fields, "customfield_22157", None)
        release_versions = getattr(self.fields, "customfield_20300", None)
        release_category = getattr(self.fields, "customfield_19502", None)
        release_title = getattr(self.fields, "customfield_19701", None)
        release_summary = getattr(self.fields, "customfield_15000", None)
        if any((release_relevant, release_change_type, release_versions, release_category, release_title, release_summary)):
            lines.append("## Release Notes")
            lines.append("")
            if release_relevant:
                lines.append(f"**Relevant for release notes:** {self.formatter.format_custom_field(release_relevant)}")
            if release_change_type:
                lines.append(f"**Change type:** {self.formatter.format_custom_field(release_change_type)}")
            if release_versions:
                lines.append(f"**Release versions:** {self.formatter.format_custom_field(release_versions)}")
            if release_category:
                lines.append(f"**Category:** {self.formatter.format_custom_field(release_category)}")
            lines.append("")
            if release_title:
                lines.append(f"**Title:** {release_title}")
                lines.append("")
            if release_summary:
                lines.append("**Summary:**")
                lines.append("")
                lines.append(self.converter.convert(release_summary))
                lines.append("")

        links = getattr(self.fields, "issuelinks", None)
        if links:
            grouped = self.formatter.format_linked_issues_grouped(links)
            if grouped:
                lines.append("## Linked Issues")
                lines.append("")
                for link_type, issue_keys in sorted(grouped.items()):
                    lines.append(f"### {link_type}")
                    lines.append("")
                    for key in issue_keys:
                        lines.append(f"- {key}")
                    lines.append("")

        lines.append("## Comments")
        lines.append("")
        lines.append(f"![[{self.issue.key}-comments-{timestamp}]]")
        lines.append("")

        return "\n".join(lines)

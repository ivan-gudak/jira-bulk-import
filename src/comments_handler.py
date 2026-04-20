"""
Comments handler module.
Fetches and formats Jira comments.
"""

from typing import List, Optional
from datetime import datetime
from jira_markup_converter import JiraMarkupConverter
from field_formatter import FieldFormatter


class CommentsHandler:
    """Handles fetching and formatting of Jira comments."""
    
    def __init__(self, jira_base_url: str, attachment_handler=None):
        """
        Initialize comments handler.
        
        Args:
            jira_base_url: Base URL for Jira instance
            attachment_handler: Optional AttachmentHandler for replacing image refs
        """
        self.converter = JiraMarkupConverter(jira_base_url)
        self.formatter = FieldFormatter()
        self.attachment_handler = attachment_handler
    
    def fetch_and_format_comments(self, issue) -> str:
        """
        Fetch and format all comments from an issue.
        
        Args:
            issue: Jira issue object
            
        Returns:
            str: Formatted comments in Markdown
        """
        if not hasattr(issue.fields, 'comment'):
            return self._generate_no_comments()
        
        comments = issue.fields.comment.comments if hasattr(issue.fields.comment, 'comments') else []
        
        if not comments:
            return self._generate_no_comments()
        
        return self._format_comments_markdown(issue.key, comments)
    
    def _generate_no_comments(self) -> str:
        """Generate markdown for no comments."""
        return "# Comments\n\n*No comments*\n"
    
    def _format_comments_markdown(self, issue_key: str, comments: List) -> str:
        """
        Format comments as Markdown.
        
        Args:
            issue_key: Jira issue key
            comments: List of comment objects
            
        Returns:
            str: Formatted markdown
        """
        lines = [f"# Comments for {issue_key}", ""]
        lines.append(f"Total comments: {len(comments)}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        for i, comment in enumerate(comments, 1):
            lines.append(self._format_single_comment(i, comment))
            lines.append("")
        
        return '\n'.join(lines)
    
    def _format_single_comment(self, number: int, comment) -> str:
        """
        Format a single comment.
        
        Args:
            number: Comment number
            comment: Jira comment object
            
        Returns:
            str: Formatted comment markdown
        """
        lines = [f"## Comment #{number}", ""]
        
        # Author
        author = self.formatter.format_user(comment.author) if hasattr(comment, 'author') else "Unknown"
        lines.append(f"**Author:** {author}")
        
        # Date
        if hasattr(comment, 'created'):
            created = self._format_datetime(comment.created)
            lines.append(f"**Created:** {created}")
        
        # Updated (if different from created)
        if hasattr(comment, 'updated') and hasattr(comment, 'created'):
            if comment.updated != comment.created:
                updated = self._format_datetime(comment.updated)
                lines.append(f"**Updated:** {updated}")
        
        lines.append("")
        
        # Comment body (convert Jira markup)
        if hasattr(comment, 'body') and comment.body:
            converted_body = self.converter.convert(comment.body)
            
            # Replace image references with downloaded attachments
            if self.attachment_handler:
                converted_body = self.attachment_handler.replace_attachment_references(converted_body)
            
            lines.append(converted_body)
        else:
            lines.append("*(Empty comment)*")
        
        lines.append("")
        lines.append("---")
        
        return '\n'.join(lines)
    
    def _format_datetime(self, dt_str: str) -> str:
        """
        Format datetime string to readable format.
        
        Args:
            dt_str: ISO datetime string
            
        Returns:
            str: Formatted datetime
        """
        try:
            # Parse ISO format
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return dt_str

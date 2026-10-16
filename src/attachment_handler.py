"""
Attachment handler module.
Downloads and manages Jira attachments.
"""

import hashlib
import json
import os
import re
import requests
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from jira_auth import describe


def _local_name(filename: str) -> str:
    """A Jira attachment name as a file name, never a path.

    The name comes from whoever attached the file: "../x" or "/abs/x" must not
    write outside the snapshot."""
    name = Path(filename.replace("\\", "/")).name
    return name if name not in ("", ".", "..") else "attachment"


class AttachmentHandler:
    """Handles downloading and processing of Jira attachments."""
    
    # Image file extensions
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.ico'}
    
    def __init__(self, jira_client, attachments_dir: str, shared_dir: Optional[str] = None):
        """
        Initialize attachment handler.
        
        Args:
            jira_client: Authenticated Jira client
            attachments_dir: Per-import directory, written only when there is no shared pool
            shared_dir: Optional shared pool directory for content-based deduplication.
                        When provided, files are stored as ``<sha256_8>_<filename>`` and
                        an attachment already pooled is not downloaded again.
        """
        self.jira_client = jira_client
        self.attachments_dir = Path(attachments_dir)
        self.shared_dir = Path(shared_dir) if shared_dir else None
        self.downloaded_files: Dict[str, str] = {}  # original_name -> local_filename
        self.image_mapping: Dict[str, str] = {}  # jira_attachment_id -> local_filename
        # Pool filename per Jira attachment ID, kept across runs. An attachment
        # ID always names the same content, so a pooled ID needs no download.
        self.pooled_by_id: Dict[str, str] = self._read_pool_record()
    
    def download_attachments(self, issue) -> Tuple[List[str], List[str]]:
        """
        Download all attachments from an issue.
        
        Args:
            issue: Jira issue object
            
        Returns:
            Tuple of (image_files, other_files)
        """
        if not hasattr(issue.fields, 'attachment'):
            return [], []
        
        attachments = issue.fields.attachment
        if not attachments:
            return [], []
        
        images = []
        others = []
        
        for attachment in attachments:
            local_filename = self._download_attachment(attachment)
            if local_filename:
                # Store mapping for reference replacement
                self.downloaded_files[attachment.filename] = local_filename
                self.image_mapping[attachment.id] = local_filename
                
                # Categorize as image or other
                if self._is_image(local_filename):
                    images.append(local_filename)
                else:
                    others.append(local_filename)

        if self.shared_dir is not None:
            self._write_pool_record()
        return images, others

    POOL_RECORD = ".attachment-ids.json"

    def _read_pool_record(self) -> Dict[str, str]:
        """Pool filenames by attachment ID from earlier runs; empty when missing or unreadable."""
        if self.shared_dir is None:
            return {}
        try:
            record = json.loads((self.shared_dir / self.POOL_RECORD).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(record, dict):
            return {}
        return {k: v for k, v in record.items() if isinstance(v, str) and v == Path(v).name}

    def _write_pool_record(self) -> None:
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        (self.shared_dir / self.POOL_RECORD).write_text(
            json.dumps(self.pooled_by_id, indent=1, sort_keys=True), encoding="utf-8"
        )
    
    def _download_attachment(self, attachment) -> Optional[str]:
        """
        Download a single attachment.
        
        When a shared pool directory is configured, the file is stored as
        ``<sha256_8>_<original_filename>``.  An attachment ID already recorded
        with a file still in the pool is reused without downloading; identical
        content under a new ID is downloaded but written only once.  If the
        shared pool is not configured the original behaviour is preserved.

        Args:
            attachment: Jira attachment object

        Returns:
            str: Local filename if successful, None otherwise
        """
        try:
            if self.shared_dir is not None:
                pooled = self.pooled_by_id.get(str(attachment.id))
                if pooled and (self.shared_dir / pooled).is_file():
                    print(f"  Reused (unchanged): {pooled}")
                    return pooled
                pooled = self._store_in_shared_pool(_local_name(attachment.filename), attachment.get())
                self.pooled_by_id[str(attachment.id)] = pooled
                return pooled

            # Legacy path: write directly to per-import attachments_dir
            content = attachment.get()
            self.attachments_dir.mkdir(parents=True, exist_ok=True)
            local_filename = self._get_unique_filename(_local_name(attachment.filename))
            local_path = self.attachments_dir / local_filename
            with open(local_path, 'wb') as f:
                f.write(content)
            print(f"  Downloaded: {local_filename}")
            return local_filename
            
        except Exception as e:
            print(f"  Warning: Failed to download {attachment.filename}: {describe(e)}")
            return None
    
    def _store_in_shared_pool(self, original_filename: str, content: bytes) -> str:
        """
        Store *content* in the shared deduplication pool.
        
        The file is written to ``shared_dir/<hash8>_<original_filename>``.
        If that path already exists the file is already identical and is
        simply reused — no disk I/O needed.
        
        Args:
            original_filename: The attachment's filename on Jira
            content: Raw file bytes
            
        Returns:
            str: Shared filename (``<hash8>_<original_filename>``)
        """
        content_hash = hashlib.sha256(content).hexdigest()[:8]
        shared_filename = f"{content_hash}_{original_filename}"
        shared_path = self.shared_dir / shared_filename
        
        if shared_path.exists():
            print(f"  Reused (unchanged): {shared_filename}")
        else:
            self.shared_dir.mkdir(parents=True, exist_ok=True)
            with open(shared_path, 'wb') as f:
                f.write(content)
            print(f"  Downloaded -> shared pool: {shared_filename}")
        
        return shared_filename
    
    def _get_unique_filename(self, filename: str) -> str:
        """
        Get unique filename, adding suffix if file exists.
        
        Args:
            filename: Original filename
            
        Returns:
            str: Unique filename
        """
        local_path = self.attachments_dir / filename
        
        if not local_path.exists():
            return filename
        
        # File exists, add counter
        name, ext = os.path.splitext(filename)
        counter = 1
        
        while True:
            new_filename = f"{name}_{counter}{ext}"
            local_path = self.attachments_dir / new_filename
            if not local_path.exists():
                return new_filename
            counter += 1
    
    def _is_image(self, filename: str) -> bool:
        """
        Check if file is an image based on extension.
        
        Args:
            filename: Filename to check
            
        Returns:
            bool: True if image
        """
        ext = Path(filename).suffix.lower()
        return ext in self.IMAGE_EXTENSIONS
    
    def replace_attachment_references(self, text: str) -> str:
        """
        Replace Jira attachment references with local Obsidian links.
        
        Args:
            text: Text with Jira attachment references
            
        Returns:
            str: Text with local Obsidian attachment references
        """
        if not text:
            return text
        
        for original_name, local_filename in self.downloaded_files.items():
            if self._is_image(local_filename):
                text = self._replace_image_reference(text, original_name, local_filename)
            else:
                text = self._replace_file_reference(text, original_name, local_filename)
        
        return text

    def replace_image_references(self, text: str) -> str:
        """Backward-compatible wrapper for attachment replacement."""
        return self.replace_attachment_references(text)

    def _replace_image_reference(self, text: str, original_name: str, local_filename: str) -> str:
        """Replace image references with Obsidian embeds."""
        escaped_name = re.escape(original_name)

        replacements = [
            (rf'!\[\]\({escaped_name}[^\)]*\)', f'![[{local_filename}]]'),
            (rf'!\[\]\(\[\]\({escaped_name}[^\)]*\)\)', f'![[{local_filename}]]'),
            (rf'\)\]\({escaped_name}\)', f'![[{local_filename}]]'),
            (rf'!{escaped_name}[^!]*!', f'![[{local_filename}]]'),
        ]

        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text)

        return text

    def _replace_file_reference(self, text: str, original_name: str, local_filename: str) -> str:
        """Replace file attachment references with Obsidian file links."""
        escaped_name = re.escape(original_name)
        escaped_caret_name = re.escape(f"^{original_name}")

        replacements = [
            (rf'(?<!\[)\[(\^{escaped_name}|{escaped_name})\]\((\^{escaped_name}|{escaped_name})\)', f'[[{local_filename}]]'),
            (rf'(?<!\[)\[(\^{escaped_name}|{escaped_name})\]\([^)]+/{escaped_name}\)', f'[[{local_filename}]]'),
            (rf'(?<!\[)\[(\^{escaped_name}|{escaped_name})\](?![\(\[])', f'[[{local_filename}]]'),
            (rf'(?<!\[\[){escaped_caret_name}(?!\]\])', f'[[{local_filename}]]'),
        ]

        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text)

        return text
    
    def get_attachment_list_markdown(self, images: List[str], others: List[str]) -> str:
        """
        Generate markdown list of attachments.
        
        Args:
            images: List of image filenames
            others: List of other filenames
            
        Returns:
            str: Markdown formatted attachment list
        """
        if not images and not others:
            return ""
        
        lines = ["## Attachments", ""]
        
        if images:
            lines.append("### Images")
            lines.append("")
            for img in images:
                lines.append(f"![[{img}]]")
                lines.append("")
        
        if others:
            lines.append("### Files")
            lines.append("")
            for file in others:
                lines.append(f"- [[{file}]]")
            lines.append("")
        
        return '\n'.join(lines)

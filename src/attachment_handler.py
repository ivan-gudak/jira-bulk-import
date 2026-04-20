"""
Attachment handler module.
Downloads and manages Jira attachments.
"""

import hashlib
import os
import re
import requests
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class AttachmentHandler:
    """Handles downloading and processing of Jira attachments."""
    
    # Image file extensions
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.ico'}
    
    def __init__(self, jira_client, attachments_dir: str, shared_dir: Optional[str] = None):
        """
        Initialize attachment handler.
        
        Args:
            jira_client: Authenticated Jira client
            attachments_dir: Per-import directory (kept for directory structure)
            shared_dir: Optional shared pool directory for content-based deduplication.
                        When provided, files are stored as ``<sha256_8>_<filename>`` and
                        identical content is never downloaded more than once.
        """
        self.jira_client = jira_client
        self.attachments_dir = Path(attachments_dir)
        self.shared_dir = Path(shared_dir) if shared_dir else None
        self.downloaded_files: Dict[str, str] = {}  # original_name -> local_filename
        self.image_mapping: Dict[str, str] = {}  # jira_attachment_id -> local_filename
    
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
        
        # Create attachments directory
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        
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
        
        return images, others
    
    def _download_attachment(self, attachment) -> Optional[str]:
        """
        Download a single attachment.
        
        When a shared pool directory is configured, the file is stored as
        ``<sha256_8>_<original_filename>``.  If an identical file already exists
        in the pool (same hash) it is reused without re-downloading.  If the
        shared pool is not configured the original behaviour is preserved.
        
        Args:
            attachment: Jira attachment object
            
        Returns:
            str: Local filename if successful, None otherwise
        """
        try:
            content = attachment.get()
            
            if self.shared_dir is not None:
                return self._store_in_shared_pool(attachment.filename, content)
            
            # Legacy path: write directly to per-import attachments_dir
            local_filename = self._get_unique_filename(attachment.filename)
            local_path = self.attachments_dir / local_filename
            with open(local_path, 'wb') as f:
                f.write(content)
            print(f"  Downloaded: {local_filename}")
            return local_filename
            
        except Exception as e:
            print(f"  Warning: Failed to download {attachment.filename}: {e}")
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

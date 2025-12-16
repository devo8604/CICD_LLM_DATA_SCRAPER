"""Comprehensive unit tests for the FileManager class."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from src.file_manager import FileManager
from src.config import AppConfig


class TestFileManagerInitialization:
    """Test cases for FileManager initialization."""

    def test_initialization(self):
        """Test FileManager initialization."""
        repos_dir = "/path/to/repos"
        max_file_size = 10 * 1024 * 1024

        file_manager = FileManager(repos_dir=repos_dir, max_file_size=max_file_size)

        assert file_manager.repos_dir == repos_dir
        assert file_manager.max_file_size == max_file_size


class TestFileManagerGetAllFilesInRepo:
    """Test cases for getting all files in repository."""

    def test_get_all_files_in_repo_simple(self):
        """Test getting files from a simple repository structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            file1 = Path(tmpdir) / "file1.py"
            file2 = Path(tmpdir) / "file2.txt"
            file1.write_text("content1")
            file2.write_text("content2")

            file_manager = FileManager(repos_dir=tmpdir, max_file_size=10 * 1024 * 1024)
            files = file_manager.get_all_files_in_repo(tmpdir)

            assert len(files) == 2
            assert str(file1) in files
            assert str(file2) in files

    def test_get_all_files_excludes_dot_files(self):
        """Test that dot files are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "visible.py"
            file2 = Path(tmpdir) / ".hidden.py"
            file1.write_text("content")
            file2.write_text("hidden")

            file_manager = FileManager(repos_dir=tmpdir, max_file_size=10 * 1024 * 1024)
            files = file_manager.get_all_files_in_repo(tmpdir)

            assert len(files) == 1
            assert str(file1) in files
            assert str(file2) not in files

    def test_get_all_files_excludes_dot_directories(self):
        """Test that files in dot directories are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .git directory with files
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            git_file = git_dir / "config"
            git_file.write_text("git config")

            # Create normal file
            normal_file = Path(tmpdir) / "readme.txt"
            normal_file.write_text("readme")

            file_manager = FileManager(repos_dir=tmpdir, max_file_size=10 * 1024 * 1024)
            files = file_manager.get_all_files_in_repo(tmpdir)

            assert len(files) == 1
            assert str(normal_file) in files
            assert str(git_file) not in files

    def test_get_all_files_excludes_large_files(self):
        """Test that files larger than max_file_size are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            small_file = Path(tmpdir) / "small.txt"
            large_file = Path(tmpdir) / "large.txt"

            small_file.write_text("small content")
            large_file.write_text("x" * (6 * 1024 * 1024))  # 6MB

            # Set max file size to 5MB
            file_manager = FileManager(repos_dir=tmpdir, max_file_size=5 * 1024 * 1024)
            files = file_manager.get_all_files_in_repo(tmpdir)

            assert len(files) == 1
            assert str(small_file) in files
            assert str(large_file) not in files

    def test_get_all_files_excludes_by_extension(self):
        """Test that files with excluded extensions are filtered out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            python_file = Path(tmpdir) / "script.py"
            image_file = Path(tmpdir) / "image.png"
            pdf_file = Path(tmpdir) / "document.pdf"

            python_file.write_text("print('hello')")
            image_file.write_bytes(b"fake image")
            pdf_file.write_bytes(b"fake pdf")

            file_manager = FileManager(repos_dir=tmpdir, max_file_size=10 * 1024 * 1024)
            files = file_manager.get_all_files_in_repo(tmpdir)

            # Only .py file should be included
            assert len(files) == 1
            assert str(python_file) in files
            assert str(image_file) not in files
            assert str(pdf_file) not in files

    def test_get_all_files_nested_directories(self):
        """Test getting files from nested directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            sub1 = Path(tmpdir) / "subdir1"
            sub2 = Path(tmpdir) / "subdir2"
            nested = sub1 / "nested"

            sub1.mkdir()
            sub2.mkdir()
            nested.mkdir()

            file1 = Path(tmpdir) / "root.py"
            file2 = sub1 / "sub1.py"
            file3 = sub2 / "sub2.py"
            file4 = nested / "nested.py"

            file1.write_text("root")
            file2.write_text("sub1")
            file3.write_text("sub2")
            file4.write_text("nested")

            file_manager = FileManager(repos_dir=tmpdir, max_file_size=10 * 1024 * 1024)
            files = file_manager.get_all_files_in_repo(tmpdir)

            assert len(files) == 4
            assert str(file1) in files
            assert str(file2) in files
            assert str(file3) in files
            assert str(file4) in files

    def test_get_all_files_returns_sorted_list(self):
        """Test that returned files are sorted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file3 = Path(tmpdir) / "zzz.py"
            file1 = Path(tmpdir) / "aaa.py"
            file2 = Path(tmpdir) / "mmm.py"

            file3.write_text("3")
            file1.write_text("1")
            file2.write_text("2")

            file_manager = FileManager(repos_dir=tmpdir, max_file_size=10 * 1024 * 1024)
            files = file_manager.get_all_files_in_repo(tmpdir)

            # Verify sorted
            assert files == sorted(files)
            assert files[0] == str(file1)
            assert files[1] == str(file2)
            assert files[2] == str(file3)

    def test_get_all_files_empty_directory(self):
        """Test getting files from empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_manager = FileManager(repos_dir=tmpdir, max_file_size=10 * 1024 * 1024)
            files = file_manager.get_all_files_in_repo(tmpdir)

            assert files == []

    def test_get_all_files_all_filtered_out(self):
        """Test when all files are filtered out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Only create files that will be filtered
            hidden = Path(tmpdir) / ".hidden"
            image = Path(tmpdir) / "image.png"

            hidden.write_text("hidden")
            image.write_bytes(b"image")

            file_manager = FileManager(repos_dir=tmpdir, max_file_size=10 * 1024 * 1024)
            files = file_manager.get_all_files_in_repo(tmpdir)

            assert files == []

    def test_get_all_files_mixed_content(self):
        """Test with mixed content types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create various file types
            python = Path(tmpdir) / "script.py"
            javascript = Path(tmpdir) / "app.js"
            text = Path(tmpdir) / "readme.txt"
            binary = Path(tmpdir) / "data.bin"
            pptx = Path(tmpdir) / "slides.pptx"

            python.write_text("python")
            javascript.write_text("js")
            text.write_text("text")
            binary.write_bytes(b"binary")
            pptx.write_bytes(b"pptx")

            file_manager = FileManager(repos_dir=tmpdir, max_file_size=10 * 1024 * 1024)
            files = file_manager.get_all_files_in_repo(tmpdir)

            # .bin and .pptx should be excluded
            assert len(files) == 3
            assert str(python) in files
            assert str(javascript) in files
            assert str(text) in files
            assert str(binary) not in files
            assert str(pptx) not in files

    def test_get_all_files_handles_symlinks(self):
        """Test that symlinks to files are handled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            real_file = Path(tmpdir) / "real.py"
            real_file.write_text("real content")

            # Create symlink
            link_file = Path(tmpdir) / "link.py"
            try:
                link_file.symlink_to(real_file)
                has_symlink = True
            except (OSError, NotImplementedError):
                # Skip on systems that don't support symlinks
                has_symlink = False

            file_manager = FileManager(repos_dir=tmpdir, max_file_size=10 * 1024 * 1024)
            files = file_manager.get_all_files_in_repo(tmpdir)

            if has_symlink:
                # Both real file and symlink should be found
                assert str(real_file) in files
            else:
                # Just the real file
                assert str(real_file) in files

    def test_get_all_files_skips_non_files(self):
        """Test that non-file entries (directories, special files) are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file
            real_file = Path(tmpdir) / "file.py"
            real_file.write_text("content")

            # Create a directory with same name pattern
            dir_path = Path(tmpdir) / "subdir"
            dir_path.mkdir()

            file_manager = FileManager(repos_dir=tmpdir, max_file_size=10 * 1024 * 1024)
            files = file_manager.get_all_files_in_repo(tmpdir)

            # Only the file should be included
            assert len(files) == 1
            assert str(real_file) in files

    def test_file_size_boundary_conditions(self):
        """Test file size filtering at boundary conditions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            max_size = 1000  # 1000 bytes

            # File exactly at max size
            exact_file = Path(tmpdir) / "exact.txt"
            exact_file.write_text("x" * max_size)

            # File just under max size
            under_file = Path(tmpdir) / "under.txt"
            under_file.write_text("x" * (max_size - 1))

            # File just over max size
            over_file = Path(tmpdir) / "over.txt"
            over_file.write_text("x" * (max_size + 1))

            file_manager = FileManager(repos_dir=tmpdir, max_file_size=max_size)
            files = file_manager.get_all_files_in_repo(tmpdir)

            # Files at or under max size should be included
            assert str(exact_file) in files
            assert str(under_file) in files
            # File over max size should be excluded
            assert str(over_file) not in files

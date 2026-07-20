import shutil
from pathlib import Path
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# Base working directory — all operations are restricted to this path
WORKDIR = Path(__file__).parents[5] / "sandbox"
WORKDIR.mkdir(parents=True, exist_ok=True)


def _safe_path(relative_path: str) -> Path:
    """Resolves the relative path inside WORKDIR and ensures it does not escape it."""
    resolved = (WORKDIR / relative_path).resolve()
    if not str(resolved).startswith(str(WORKDIR.resolve())):
        raise ValueError(f"Access denied: path '{relative_path}' is outside the allowed working directory.")
    return resolved


# ── Schemas ────────────────────────────────────────────────────────────────────

class ReadDirectoryInput(BaseModel):
    path: str = Field(default=".", description="Relative path to the directory to list. Use '.' for the root.")
    recursive: bool = Field(default=False, description="If true, recursively lists all subdirectories.")

class ReadFileInput(BaseModel):
    path: str = Field(description="Relative path to the file to be read.")

class WriteFileInput(BaseModel):
    path: str = Field(description="Relative path to the file to be created or overwritten.")
    content: str = Field(description="Content to write to the file.")

class UpdateFileInput(BaseModel):
    path: str = Field(description="Relative path to the file to be updated.")
    content: str = Field(description="Content to be appended to the end of the file.")

class MoveFileInput(BaseModel):
    source: str = Field(description="Relative path to the source file.")
    destination: str = Field(description="Relative path to the destination file.")

class DeleteFileInput(BaseModel):
    path: str = Field(description="Relative path to the file to be deleted.")

class CreateFolderInput(BaseModel):
    path: str = Field(description="Relative path to the directory to be created.")

class DeleteFolderInput(BaseModel):
    path: str = Field(description="Relative path to the directory to be deleted.")

class MoveFolderInput(BaseModel):
    source: str = Field(description="Relative path to the source directory.")
    destination: str = Field(description="Relative path to the destination directory.")

class SearchFilesByNameInput(BaseModel):
    directory: str = Field(default=".", description="Relative path to the directory to search in.")
    pattern: str = Field(description="Search pattern for the filename (supports wildcards like *.txt or *config*).")
    recursive: bool = Field(default=True, description="If true, searches recursively in subdirectories.")

class SearchKeywordInFileInput(BaseModel):
    path: str = Field(description="Relative path to the file to search in.")
    keyword: str = Field(description="Keyword to search for in the file.")
    case_sensitive: bool = Field(default=False, description="If true, search is case-sensitive.")

class ReadFileRangeInput(BaseModel):
    path: str = Field(description="Relative path to the file to be read.")
    start_line: int = Field(description="Starting line number (beginning at 1).")
    end_line: int = Field(description="Ending line number (inclusive).")


# ── Tools ────────────────────────────────────────────────────────────────────

@tool(args_schema=ReadDirectoryInput)
def read_directory(path: str = ".", recursive: bool = False) -> str:
    """Lists files and folders in a directory inside the working directory."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Error: directory '{path}' does not exist."
        if not target.is_dir():
            return f"Error: '{path}' is not a directory."

        if recursive:
            entries = [str(p.relative_to(WORKDIR)) for p in sorted(target.rglob("*"))]
        else:
            entries = [str(p.relative_to(WORKDIR)) for p in sorted(target.iterdir())]

        if not entries:
            return f"Directory '{path}' is empty."
        return "Contents listed successfully:\n" + "\n".join(entries)
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error listing directory: {e}"


@tool(args_schema=ReadFileInput)
def read_file(path: str) -> str:
    """Reads and returns the contents of a file inside the working directory."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Error: file '{path}' does not exist."
        if not target.is_file():
            return f"Error: '{path}' is not a file."
        content = target.read_text(encoding="utf-8")
        return f"Contents of file '{path}':\n{content}"
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"


@tool(args_schema=WriteFileInput)
def write_file(path: str, content: str) -> str:
    """Creates a file with the provided content inside the working directory."""
    try:
        target = _safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"File '{path}' created successfully."
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool(args_schema=UpdateFileInput)
def update_file(path: str, content: str) -> str:
    """Appends content to an existing file inside the working directory."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Error: file '{path}' does not exist. Use write_file to create it."
        with target.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"Content appended successfully to file '{path}'."
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error appending content: {e}"


@tool(args_schema=MoveFileInput)
def move_file(source: str, destination: str) -> str:
    """Moves a file from one path to another inside the working directory."""
    try:
        src = _safe_path(source)
        dst = _safe_path(destination)
        if not src.exists():
            return f"Error: source file '{source}' does not exist."
        if not src.is_file():
            return f"Error: '{source}' is not a file."
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"File moved successfully: '{source}' → '{destination}'."
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error moving file: {e}"


@tool(args_schema=DeleteFileInput)
def delete_file(path: str) -> str:
    """Deletes a file inside the working directory."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Error: file '{path}' does not exist."
        if not target.is_file():
            return f"Error: '{path}' is not a file."
        target.unlink()
        return f"File '{path}' deleted successfully."
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error deleting file: {e}"


@tool(args_schema=CreateFolderInput)
def create_folder(path: str) -> str:
    """Creates a new directory inside the working directory."""
    try:
        target = _safe_path(path)
        if target.exists():
            return f"Warning: directory '{path}' already exists."
        target.mkdir(parents=True, exist_ok=True)
        return f"Directory '{path}' created successfully."
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error creating directory: {e}"


@tool(args_schema=DeleteFolderInput)
def delete_folder(path: str) -> str:
    """Deletes a directory and all its contents inside the working directory."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Error: directory '{path}' does not exist."
        if not target.is_dir():
            return f"Error: '{path}' is not a directory."
        shutil.rmtree(target)
        return f"Directory '{path}' and all its contents deleted successfully."
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error deleting directory: {e}"


@tool(args_schema=MoveFolderInput)
def move_folder(source: str, destination: str) -> str:
    """Moves a directory from one path to another inside the working directory."""
    try:
        src = _safe_path(source)
        dst = _safe_path(destination)
        if not src.exists():
            return f"Error: source directory '{source}' does not exist."
        if not src.is_dir():
            return f"Error: '{source}' is not a directory."
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Directory moved successfully: '{source}' → '{destination}'."
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error moving directory: {e}"


@tool(args_schema=SearchFilesByNameInput)
def search_files_by_name(directory: str = ".", pattern: str = "*", recursive: bool = True) -> str:
    """
    Searches for files by name in a directory using patterns (wildcards).

    Pattern examples:
    - '*.py' → all .py files
    - '*config*' → files with 'config' in the name
    - 'test_*.txt' → files starting with 'test_' and ending with .txt
    """
    try:
        target = _safe_path(directory)
        if not target.exists():
            return f"Error: directory '{directory}' does not exist."
        if not target.is_dir():
            return f"Error: '{directory}' is not a directory."

        # Search files using glob pattern
        if recursive:
            matches = list(target.rglob(pattern))
        else:
            matches = list(target.glob(pattern))

        # Filter only files (not directories)
        file_matches = [p for p in matches if p.is_file()]

        if not file_matches:
            return f"No files found with pattern '{pattern}' in '{directory}'."

        # Format result with relative paths
        result_lines = [str(p.relative_to(WORKDIR)) for p in sorted(file_matches)]

        return f"Found {len(file_matches)} matching file(s):\n" + "\n".join(result_lines)
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error searching files: {e}"


@tool(args_schema=SearchKeywordInFileInput)
def search_keyword_in_file(path: str, keyword: str, case_sensitive: bool = False) -> str:
    """
    Searches for a keyword inside a file and returns the matching lines with their numbers.

    Returns each occurrence with the line number and the full line content.
    """
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Error: file '{path}' does not exist."
        if not target.is_file():
            return f"Error: '{path}' is not a file."

        content = target.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Perform the search
        keyword_to_search = keyword if case_sensitive else keyword.lower()
        matches = []

        for line_num, line in enumerate(lines, start=1):
            line_to_search = line if case_sensitive else line.lower()
            if keyword_to_search in line_to_search:
                matches.append(f"Line {line_num}: {line}")

        if not matches:
            return f"No occurrences of keyword '{keyword}' found in file '{path}'."

        return f"Found {len(matches)} occurrence(s) of '{keyword}' in file '{path}':\n\n" + "\n".join(matches)
    except UnicodeDecodeError:
        return f"Error: file '{path}' cannot be read as text."
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error searching keyword: {e}"


@tool(args_schema=ReadFileRangeInput)
def read_file_range(path: str, start_line: int, end_line: int) -> str:
    """
    Reads and returns only a specific range of lines from a file.

    Useful for viewing specific sections of large files without loading everything.
    Lines are numbered starting at 1.
    """
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Error: file '{path}' does not exist."
        if not target.is_file():
            return f"Error: '{path}' is not a file."

        # Validate line numbers
        if start_line < 1:
            return "Error: start_line must be >= 1."
        if end_line < start_line:
            return "Error: end_line must be >= start_line."

        content = target.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Check if the range is within the file
        total_lines = len(lines)
        if start_line > total_lines:
            return f"Error: file '{path}' has only {total_lines} line(s), but start_line={start_line} was requested."

        # Adjust end_line if greater than total
        actual_end = min(end_line, total_lines)

        # Extract the range (converting to 0-based index)
        selected_lines = lines[start_line - 1:actual_end]

        # Format with line numbers
        formatted_lines = [
            f"{line_num}: {line}"
            for line_num, line in enumerate(selected_lines, start=start_line)
        ]

        return (
            f"Lines {start_line}-{actual_end} of file '{path}' "
            f"(total: {total_lines} lines):\n\n" +
            "\n".join(formatted_lines)
        )
    except UnicodeDecodeError:
        return f"Error: file '{path}' cannot be read as text."
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error reading file range: {e}"


def get_custom_filesystem_tools():
    return [
        read_directory,
        read_file,
        write_file,
        update_file,
        move_file,
        delete_file,
        create_folder,
        delete_folder,
        move_folder,
        search_files_by_name,
        search_keyword_in_file,
        read_file_range,
    ]

def get_discovery_filesystem_tools():
    return [
        read_directory,
        read_file,
        search_files_by_name,
        search_keyword_in_file,
        read_file_range,
    ]

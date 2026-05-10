import shutil
from pathlib import Path
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# Diretório base de trabalho — todas as operações ficam restritas a este caminho
WORKDIR = Path(__file__).parents[5] / "sandbox"
WORKDIR.mkdir(parents=True, exist_ok=True)


def _safe_path(relative_path: str) -> Path:
    """Resolve o caminho relativo dentro do WORKDIR e garante que não escapa dele."""
    resolved = (WORKDIR / relative_path).resolve()
    if not str(resolved).startswith(str(WORKDIR.resolve())):
        raise ValueError(f"Acesso negado: o caminho '{relative_path}' está fora do diretório de trabalho permitido.")
    return resolved


# ── Schemas ────────────────────────────────────────────────────────────────────

class ReadDirectoryInput(BaseModel):
    path: str = Field(default=".", description="Caminho relativo ao diretório para listar. Use '.' para a raiz.")
    recursive: bool = Field(default=False, description="Se verdadeiro, lista recursivamente todos os subdiretórios.")

class ReadFileInput(BaseModel):
    path: str = Field(description="Caminho relativo ao diretório do arquivo a ser lido.")

class WriteFileInput(BaseModel):
    path: str = Field(description="Caminho relativo ao diretório do arquivo a ser criado ou sobrescrito.")
    content: str = Field(description="Conteúdo a ser escrito no arquivo.")

class UpdateFileInput(BaseModel):
    path: str = Field(description="Caminho relativo ao diretório do arquivo a ser atualizado.")
    content: str = Field(description="Conteúdo a ser acrescentado ao final do arquivo.")

class MoveFileInput(BaseModel):
    source: str = Field(description="Caminho relativo ao diretório do arquivo de origem.")
    destination: str = Field(description="Caminho relativo ao diretório do arquivo de destino.")

class DeleteFileInput(BaseModel):
    path: str = Field(description="Caminho relativo ao diretório do arquivo a ser apagado.")

class CreateFolderInput(BaseModel):
    path: str = Field(description="Caminho relativo ao diretório a ser criado.")

class DeleteFolderInput(BaseModel):
    path: str = Field(description="Caminho relativo ao diretório a ser apagado.")

class MoveFolderInput(BaseModel):
    source: str = Field(description="Caminho relativo ao diretório de origem.")
    destination: str = Field(description="Caminho relativo ao diretório de destino.")

class SearchFilesByNameInput(BaseModel):
    directory: str = Field(default=".", description="Caminho relativo ao diretório onde buscar.")
    pattern: str = Field(description="Padrão de busca para o nome do arquivo (suporta wildcards como *.txt ou *config*).")
    recursive: bool = Field(default=True, description="Se verdadeiro, busca recursivamente em subdiretórios.")

class SearchKeywordInFileInput(BaseModel):
    path: str = Field(description="Caminho relativo ao arquivo onde buscar.")
    keyword: str = Field(description="Palavra-chave a ser buscada no arquivo.")
    case_sensitive: bool = Field(default=False, description="Se verdadeiro, busca diferencia maiúsculas de minúsculas.")

class ReadFileRangeInput(BaseModel):
    path: str = Field(description="Caminho relativo ao arquivo a ser lido.")
    start_line: int = Field(description="Número da linha inicial (começando em 1).")
    end_line: int = Field(description="Número da linha final (inclusivo).")


# ── Ferramentas ────────────────────────────────────────────────────────────────

@tool(args_schema=ReadDirectoryInput)
def read_directory(path: str = ".", recursive: bool = False) -> str:
    """Lista os arquivos e pastas de um diretório dentro do diretório."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Erro: o diretório '{path}' não existe."
        if not target.is_dir():
            return f"Erro: '{path}' não é um diretório."

        if recursive:
            entries = [str(p.relative_to(WORKDIR)) for p in sorted(target.rglob("*"))]
        else:
            entries = [str(p.relative_to(WORKDIR)) for p in sorted(target.iterdir())]

        if not entries:
            return f"Diretório '{path}' está vazio."
        return "Conteúdo listado com sucesso:\n" + "\n".join(entries)
    except ValueError as e:
        return f"Erro de segurança: {e}"
    except Exception as e:
        return f"Erro ao listar diretório: {e}"


@tool(args_schema=ReadFileInput)
def read_file(path: str) -> str:
    """Lê e retorna o conteúdo de um arquivo dentro do diretório."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Erro: o arquivo '{path}' não existe."
        if not target.is_file():
            return f"Erro: '{path}' não é um arquivo."
        content = target.read_text(encoding="utf-8")
        return f"Conteúdo do arquivo '{path}':\n{content}"
    except ValueError as e:
        return f"Erro de segurança: {e}"
    except Exception as e:
        return f"Erro ao ler arquivo: {e}"


@tool(args_schema=WriteFileInput)
def write_file(path: str, content: str) -> str:
    """Criar um arquivo com o conteúdo fornecido dentro do diretório."""
    try:
        target = _safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Arquivo '{path}' criado com sucesso."
    except ValueError as e:
        return f"Erro de segurança: {e}"
    except Exception as e:
        return f"Erro ao escrever arquivo: {e}"


@tool(args_schema=UpdateFileInput)
def update_file(path: str, content: str) -> str:
    """Modifica o conteúdo de um arquivo existente dentro do diretório."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Erro: o arquivo '{path}' não existe. Use write_file para criar."
        with target.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"Conteúdo modificado com sucesso no arquivo '{path}'."
    except ValueError as e:
        return f"Erro de segurança: {e}"
    except Exception as e:
        return f"Erro ao modificar conteúdo: {e}"


@tool(args_schema=MoveFileInput)
def move_file(source: str, destination: str) -> str:
    """Move um arquivo de um caminho para outro dentro do diretório."""
    try:
        src = _safe_path(source)
        dst = _safe_path(destination)
        if not src.exists():
            return f"Erro: o arquivo de origem '{source}' não existe."
        if not src.is_file():
            return f"Erro: '{source}' não é um arquivo."
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Arquivo movido com sucesso: '{source}' → '{destination}'."
    except ValueError as e:
        return f"Erro de segurança: {e}"
    except Exception as e:
        return f"Erro ao mover arquivo: {e}"


@tool(args_schema=DeleteFileInput)
def delete_file(path: str) -> str:
    """Apaga um arquivo dentro do diretório."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Erro: o arquivo '{path}' não existe."
        if not target.is_file():
            return f"Erro: '{path}' não é um arquivo."
        target.unlink()
        return f"Arquivo '{path}' apagado com sucesso."
    except ValueError as e:
        return f"Erro de segurança: {e}"
    except Exception as e:
        return f"Erro ao apagar arquivo: {e}"


@tool(args_schema=CreateFolderInput)
def create_folder(path: str) -> str:
    """Cria um novo diretório dentro do diretório."""
    try:
        target = _safe_path(path)
        if target.exists():
            return f"Aviso: o diretório '{path}' já existe."
        target.mkdir(parents=True, exist_ok=True)
        return f"Diretório '{path}' criado com sucesso."
    except ValueError as e:
        return f"Erro de segurança: {e}"
    except Exception as e:
        return f"Erro ao criar diretório: {e}"


@tool(args_schema=DeleteFolderInput)
def delete_folder(path: str) -> str:
    """Apaga um diretório e todo seu conteúdo dentro do diretório."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Erro: o diretório '{path}' não existe."
        if not target.is_dir():
            return f"Erro: '{path}' não é um diretório."
        shutil.rmtree(target)
        return f"Diretório '{path}' e todo seu conteúdo foram apagados com sucesso."
    except ValueError as e:
        return f"Erro de segurança: {e}"
    except Exception as e:
        return f"Erro ao apagar diretório: {e}"


@tool(args_schema=MoveFolderInput)
def move_folder(source: str, destination: str) -> str:
    """Move um diretório de um caminho para outro dentro do diretório."""
    try:
        src = _safe_path(source)
        dst = _safe_path(destination)
        if not src.exists():
            return f"Erro: o diretório de origem '{source}' não existe."
        if not src.is_dir():
            return f"Erro: '{source}' não é um diretório."
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Diretório movido com sucesso: '{source}' → '{destination}'."
    except ValueError as e:
        return f"Erro de segurança: {e}"
    except Exception as e:
        return f"Erro ao mover diretório: {e}"


@tool(args_schema=SearchFilesByNameInput)
def search_files_by_name(directory: str = ".", pattern: str = "*", recursive: bool = True) -> str:
    """
    Busca arquivos por nome similar em um diretório usando padrões (wildcards).
    
    Exemplos de padrões:
    - '*.py' → todos os arquivos .py
    - '*config*' → arquivos com 'config' no nome
    - 'test_*.txt' → arquivos que começam com 'test_' e terminam com .txt
    """
    try:
        target = _safe_path(directory)
        if not target.exists():
            return f"Erro: o diretório '{directory}' não existe."
        if not target.is_dir():
            return f"Erro: '{directory}' não é um diretório."

        # Busca arquivos usando glob pattern
        if recursive:
            matches = list(target.rglob(pattern))
        else:
            matches = list(target.glob(pattern))
        
        # Filtra apenas arquivos (não diretórios)
        file_matches = [p for p in matches if p.is_file()]
        
        if not file_matches:
            return f"Nenhum arquivo encontrado com o padrão '{pattern}' em '{directory}'."
        
        # Formata resultado com caminhos relativos
        result_lines = [str(p.relative_to(WORKDIR)) for p in sorted(file_matches)]
        
        return f"Encontrados {len(file_matches)} arquivo(s) correspondente(s):\n" + "\n".join(result_lines)
    except ValueError as e:
        return f"Erro de segurança: {e}"
    except Exception as e:
        return f"Erro ao buscar arquivos: {e}"


@tool(args_schema=SearchKeywordInFileInput)
def search_keyword_in_file(path: str, keyword: str, case_sensitive: bool = False) -> str:
    """
    Busca uma palavra-chave dentro de um arquivo e retorna as linhas encontradas com seus números.
    
    Retorna cada ocorrência com o número da linha e o conteúdo completo da linha.
    """
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Erro: o arquivo '{path}' não existe."
        if not target.is_file():
            return f"Erro: '{path}' não é um arquivo."
        
        content = target.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        # Realiza a busca
        keyword_to_search = keyword if case_sensitive else keyword.lower()
        matches = []
        
        for line_num, line in enumerate(lines, start=1):
            line_to_search = line if case_sensitive else line.lower()
            if keyword_to_search in line_to_search:
                matches.append(f"Linha {line_num}: {line}")
        
        if not matches:
            return f"Nenhuma ocorrência da palavra-chave '{keyword}' encontrada no arquivo '{path}'."
        
        return f"Encontradas {len(matches)} ocorrência(s) de '{keyword}' no arquivo '{path}':\n\n" + "\n".join(matches)
    except UnicodeDecodeError:
        return f"Erro: o arquivo '{path}' não pode ser lido como texto."
    except ValueError as e:
        return f"Erro de segurança: {e}"
    except Exception as e:
        return f"Erro ao buscar palavra-chave: {e}"


@tool(args_schema=ReadFileRangeInput)
def read_file_range(path: str, start_line: int, end_line: int) -> str:
    """
    Lê e retorna apenas um range específico de linhas de um arquivo.
    
    Útil para visualizar trechos específicos de arquivos grandes sem carregar tudo.
    As linhas são numeradas começando em 1.
    """
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Erro: o arquivo '{path}' não existe."
        if not target.is_file():
            return f"Erro: '{path}' não é um arquivo."
        
        # Validação dos números de linha
        if start_line < 1:
            return "Erro: start_line deve ser >= 1."
        if end_line < start_line:
            return "Erro: end_line deve ser >= start_line."
        
        content = target.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        # Verifica se o range está dentro do arquivo
        total_lines = len(lines)
        if start_line > total_lines:
            return f"Erro: o arquivo '{path}' tem apenas {total_lines} linha(s), mas foi solicitado a partir da linha {start_line}."
        
        # Ajusta end_line se for maior que o total
        actual_end = min(end_line, total_lines)
        
        # Extrai o range (convertendo para índice 0-based)
        selected_lines = lines[start_line - 1:actual_end]
        
        # Formata com números de linha
        formatted_lines = [
            f"{line_num}: {line}" 
            for line_num, line in enumerate(selected_lines, start=start_line)
        ]
        
        return (
            f"Linhas {start_line}-{actual_end} do arquivo '{path}' "
            f"(total: {total_lines} linhas):\n\n" + 
            "\n".join(formatted_lines)
        )
    except UnicodeDecodeError:
        return f"Erro: o arquivo '{path}' não pode ser lido como texto."
    except ValueError as e:
        return f"Erro de segurança: {e}"
    except Exception as e:
        return f"Erro ao ler range do arquivo: {e}"


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
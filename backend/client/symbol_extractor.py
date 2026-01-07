"""Tree-sitter based symbol extractor for cross-file validation.

Extracts defined symbols (classes, functions, variables, constants) from source files
to help LLM validate imports and API calls across files.

Supports multiple languages through tree-sitter grammars.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field, asdict

from utils.logger import get_logger

logger = get_logger(__name__)

# Try to import tree-sitter
try:
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript
    import tree_sitter_go
    import tree_sitter_java
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning("tree-sitter not available. Install with: pip install tree-sitter tree-sitter-python tree-sitter-javascript tree-sitter-typescript tree-sitter-go tree-sitter-java")


@dataclass
class SymbolInfo:
    """Information about a defined symbol."""
    name: str
    kind: str  # class, function, method, variable, constant, interface, type
    line: int
    exported: bool = True  # Whether the symbol is exported/public
    parent: Optional[str] = None  # Parent class/module for methods
    parameters: List[str] = field(default_factory=list)  # For functions/methods

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FileSymbols:
    """Symbols defined in a single file."""
    file_path: str
    language: str
    symbols: List[SymbolInfo] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)  # What this file imports
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'file_path': self.file_path,
            'language': self.language,
            'symbols': [s.to_dict() for s in self.symbols],
            'imports': self.imports,
            'errors': self.errors,
        }

    def get_exported_names(self) -> Set[str]:
        """Get all exported symbol names."""
        return {s.name for s in self.symbols if s.exported}


class SymbolExtractor:
    """Extract symbols from source files using tree-sitter."""

    # Language detection by extension
    EXTENSION_MAP = {
        '.py': 'python',
        '.pyi': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.go': 'go',
        '.java': 'java',
    }

    def __init__(self):
        """Initialize the symbol extractor."""
        self._parsers: Dict[str, Parser] = {}
        self._available = TREE_SITTER_AVAILABLE

        if self._available:
            self._init_parsers()

    def _init_parsers(self):
        """Initialize tree-sitter parsers for each language."""
        try:
            # Python
            self._parsers['python'] = Parser(Language(tree_sitter_python.language()))
            logger.debug("Initialized Python parser")
        except Exception as e:
            logger.warning(f"Failed to init Python parser: {e}")

        try:
            # JavaScript
            self._parsers['javascript'] = Parser(Language(tree_sitter_javascript.language()))
            logger.debug("Initialized JavaScript parser")
        except Exception as e:
            logger.warning(f"Failed to init JavaScript parser: {e}")

        try:
            # TypeScript
            ts_lang = Language(tree_sitter_typescript.language_typescript())
            self._parsers['typescript'] = Parser(ts_lang)
            tsx_lang = Language(tree_sitter_typescript.language_tsx())
            self._parsers['tsx'] = Parser(tsx_lang)
            logger.debug("Initialized TypeScript parser")
        except Exception as e:
            logger.warning(f"Failed to init TypeScript parser: {e}")

        try:
            # Go
            self._parsers['go'] = Parser(Language(tree_sitter_go.language()))
            logger.debug("Initialized Go parser")
        except Exception as e:
            logger.warning(f"Failed to init Go parser: {e}")

        try:
            # Java
            self._parsers['java'] = Parser(Language(tree_sitter_java.language()))
            logger.debug("Initialized Java parser")
        except Exception as e:
            logger.warning(f"Failed to init Java parser: {e}")

        logger.info(f"Symbol extractor initialized with parsers: {list(self._parsers.keys())}")

    def _detect_language(self, filename: str) -> Optional[str]:
        """Detect language from filename."""
        ext = Path(filename).suffix.lower()
        lang = self.EXTENSION_MAP.get(ext)
        # Handle TSX separately
        if ext == '.tsx':
            return 'tsx'
        return lang

    def _get_parser(self, language: str) -> Optional[Parser]:
        """Get parser for a language."""
        return self._parsers.get(language)

    def extract_symbols(self, filename: str, content: str) -> FileSymbols:
        """Extract symbols from a single file.

        Args:
            filename: File path
            content: File content

        Returns:
            FileSymbols object with extracted symbols
        """
        language = self._detect_language(filename)
        result = FileSymbols(file_path=filename, language=language or 'unknown')

        if not self._available:
            result.errors.append("tree-sitter not available")
            return result

        if not language:
            result.errors.append(f"Unsupported file type: {filename}")
            return result

        parser = self._get_parser(language)
        if not parser:
            result.errors.append(f"No parser for language: {language}")
            return result

        try:
            tree = parser.parse(content.encode('utf-8'))
            root = tree.root_node

            # Extract symbols based on language
            if language == 'python':
                self._extract_python_symbols(root, content, result)
            elif language in ('javascript', 'typescript', 'tsx'):
                self._extract_js_ts_symbols(root, content, result)
            elif language == 'go':
                self._extract_go_symbols(root, content, result)
            elif language == 'java':
                self._extract_java_symbols(root, content, result)

        except Exception as e:
            logger.warning(f"Error parsing {filename}: {e}")
            result.errors.append(str(e))

        return result

    def _extract_python_symbols(self, root, content: str, result: FileSymbols):
        """Extract symbols from Python AST."""
        def visit(node, parent_class=None):
            # Class definition
            if node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = content[name_node.start_byte:name_node.end_byte]
                    exported = not class_name.startswith('_')
                    result.symbols.append(SymbolInfo(
                        name=class_name,
                        kind='class',
                        line=node.start_point[0] + 1,
                        exported=exported,
                    ))
                    # Visit methods within class
                    for child in node.children:
                        visit(child, class_name)
                    return

            # Function definition
            if node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = content[name_node.start_byte:name_node.end_byte]
                    exported = not func_name.startswith('_')
                    params = self._extract_python_params(node, content)

                    kind = 'method' if parent_class else 'function'
                    result.symbols.append(SymbolInfo(
                        name=func_name,
                        kind=kind,
                        line=node.start_point[0] + 1,
                        exported=exported,
                        parent=parent_class,
                        parameters=params,
                    ))
                return

            # Assignment (top-level variables/constants)
            if node.type == 'assignment' and node.parent and node.parent.type == 'module':
                left = node.child_by_field_name('left')
                if left and left.type == 'identifier':
                    var_name = content[left.start_byte:left.end_byte]
                    exported = not var_name.startswith('_')
                    # Constants are UPPER_CASE
                    kind = 'constant' if var_name.isupper() else 'variable'
                    result.symbols.append(SymbolInfo(
                        name=var_name,
                        kind=kind,
                        line=node.start_point[0] + 1,
                        exported=exported,
                    ))
                return

            # Import statements
            if node.type in ('import_statement', 'import_from_statement'):
                import_text = content[node.start_byte:node.end_byte]
                result.imports.append(import_text)
                return

            # Recurse
            for child in node.children:
                visit(child, parent_class)

        visit(root)

    def _extract_python_params(self, func_node, content: str) -> List[str]:
        """Extract parameter names from Python function."""
        params = []
        params_node = func_node.child_by_field_name('parameters')
        if params_node:
            for child in params_node.children:
                if child.type == 'identifier':
                    params.append(content[child.start_byte:child.end_byte])
                elif child.type in ('default_parameter', 'typed_parameter', 'typed_default_parameter'):
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        params.append(content[name_node.start_byte:name_node.end_byte])
        return params

    def _extract_js_ts_symbols(self, root, content: str, result: FileSymbols):
        """Extract symbols from JavaScript/TypeScript AST."""
        def visit(node, parent_class=None, is_exported=False):
            # Export statement
            if node.type in ('export_statement', 'export_default_declaration'):
                for child in node.children:
                    visit(child, parent_class, is_exported=True)
                return

            # Class declaration
            if node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = content[name_node.start_byte:name_node.end_byte]
                    result.symbols.append(SymbolInfo(
                        name=class_name,
                        kind='class',
                        line=node.start_point[0] + 1,
                        exported=is_exported,
                    ))
                    # Visit methods
                    body = node.child_by_field_name('body')
                    if body:
                        for child in body.children:
                            visit(child, class_name, is_exported)
                return

            # Function declaration
            if node.type in ('function_declaration', 'function'):
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = content[name_node.start_byte:name_node.end_byte]
                    params = self._extract_js_params(node, content)
                    result.symbols.append(SymbolInfo(
                        name=func_name,
                        kind='function',
                        line=node.start_point[0] + 1,
                        exported=is_exported,
                        parameters=params,
                    ))
                return

            # Method definition (in class)
            if node.type == 'method_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    method_name = content[name_node.start_byte:name_node.end_byte]
                    params = self._extract_js_params(node, content)
                    result.symbols.append(SymbolInfo(
                        name=method_name,
                        kind='method',
                        line=node.start_point[0] + 1,
                        exported=True,
                        parent=parent_class,
                        parameters=params,
                    ))
                return

            # Variable declaration (const, let, var)
            if node.type == 'lexical_declaration' or node.type == 'variable_declaration':
                for child in node.children:
                    if child.type == 'variable_declarator':
                        name_node = child.child_by_field_name('name')
                        if name_node and name_node.type == 'identifier':
                            var_name = content[name_node.start_byte:name_node.end_byte]
                            # Check if it's a const (constant)
                            kind = 'constant' if 'const' in content[node.start_byte:node.start_byte+10] else 'variable'
                            result.symbols.append(SymbolInfo(
                                name=var_name,
                                kind=kind,
                                line=node.start_point[0] + 1,
                                exported=is_exported,
                            ))
                return

            # Interface (TypeScript)
            if node.type == 'interface_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    interface_name = content[name_node.start_byte:name_node.end_byte]
                    result.symbols.append(SymbolInfo(
                        name=interface_name,
                        kind='interface',
                        line=node.start_point[0] + 1,
                        exported=is_exported,
                    ))
                return

            # Type alias (TypeScript)
            if node.type == 'type_alias_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    type_name = content[name_node.start_byte:name_node.end_byte]
                    result.symbols.append(SymbolInfo(
                        name=type_name,
                        kind='type',
                        line=node.start_point[0] + 1,
                        exported=is_exported,
                    ))
                return

            # Import statements
            if node.type == 'import_statement':
                import_text = content[node.start_byte:node.end_byte]
                result.imports.append(import_text)
                return

            # Recurse
            for child in node.children:
                visit(child, parent_class, is_exported)

        visit(root)

    def _extract_js_params(self, func_node, content: str) -> List[str]:
        """Extract parameter names from JS/TS function."""
        params = []
        params_node = func_node.child_by_field_name('parameters')
        if params_node:
            for child in params_node.children:
                if child.type == 'identifier':
                    params.append(content[child.start_byte:child.end_byte])
                elif child.type in ('required_parameter', 'optional_parameter'):
                    # TypeScript typed params
                    pattern = child.child_by_field_name('pattern')
                    if pattern and pattern.type == 'identifier':
                        params.append(content[pattern.start_byte:pattern.end_byte])
        return params

    def _extract_go_symbols(self, root, content: str, result: FileSymbols):
        """Extract symbols from Go AST."""
        def visit(node):
            # Function declaration
            if node.type == 'function_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = content[name_node.start_byte:name_node.end_byte]
                    exported = func_name[0].isupper() if func_name else False
                    params = self._extract_go_params(node, content)
                    result.symbols.append(SymbolInfo(
                        name=func_name,
                        kind='function',
                        line=node.start_point[0] + 1,
                        exported=exported,
                        parameters=params,
                    ))
                return

            # Method declaration (with receiver)
            if node.type == 'method_declaration':
                name_node = node.child_by_field_name('name')
                receiver = node.child_by_field_name('receiver')
                if name_node:
                    method_name = content[name_node.start_byte:name_node.end_byte]
                    exported = method_name[0].isupper() if method_name else False
                    params = self._extract_go_params(node, content)

                    # Get receiver type
                    parent_type = None
                    if receiver:
                        for child in receiver.children:
                            if child.type == 'parameter_declaration':
                                type_node = child.child_by_field_name('type')
                                if type_node:
                                    parent_type = content[type_node.start_byte:type_node.end_byte].strip('*')

                    result.symbols.append(SymbolInfo(
                        name=method_name,
                        kind='method',
                        line=node.start_point[0] + 1,
                        exported=exported,
                        parent=parent_type,
                        parameters=params,
                    ))
                return

            # Type declaration (struct, interface)
            if node.type == 'type_declaration':
                for child in node.children:
                    if child.type == 'type_spec':
                        name_node = child.child_by_field_name('name')
                        type_node = child.child_by_field_name('type')
                        if name_node:
                            type_name = content[name_node.start_byte:name_node.end_byte]
                            exported = type_name[0].isupper() if type_name else False
                            kind = 'interface' if type_node and type_node.type == 'interface_type' else 'class'
                            result.symbols.append(SymbolInfo(
                                name=type_name,
                                kind=kind,
                                line=node.start_point[0] + 1,
                                exported=exported,
                            ))
                return

            # Const/Var declarations
            if node.type in ('const_declaration', 'var_declaration'):
                kind = 'constant' if node.type == 'const_declaration' else 'variable'
                for child in node.children:
                    if child.type == 'const_spec' or child.type == 'var_spec':
                        name_node = child.child_by_field_name('name')
                        if name_node:
                            var_name = content[name_node.start_byte:name_node.end_byte]
                            exported = var_name[0].isupper() if var_name else False
                            result.symbols.append(SymbolInfo(
                                name=var_name,
                                kind=kind,
                                line=node.start_point[0] + 1,
                                exported=exported,
                            ))
                return

            # Import declarations
            if node.type == 'import_declaration':
                import_text = content[node.start_byte:node.end_byte]
                result.imports.append(import_text)
                return

            # Recurse
            for child in node.children:
                visit(child)

        visit(root)

    def _extract_go_params(self, func_node, content: str) -> List[str]:
        """Extract parameter names from Go function."""
        params = []
        params_node = func_node.child_by_field_name('parameters')
        if params_node:
            for child in params_node.children:
                if child.type == 'parameter_declaration':
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        params.append(content[name_node.start_byte:name_node.end_byte])
        return params

    def _extract_java_symbols(self, root, content: str, result: FileSymbols):
        """Extract symbols from Java AST."""
        def get_modifiers(node) -> Set[str]:
            """Get modifiers (public, private, static, etc.)"""
            mods = set()
            for child in node.children:
                if child.type == 'modifiers':
                    mods_text = content[child.start_byte:child.end_byte]
                    for m in ['public', 'private', 'protected', 'static', 'final']:
                        if m in mods_text:
                            mods.add(m)
            return mods

        def visit(node, parent_class=None):
            # Class declaration
            if node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = content[name_node.start_byte:name_node.end_byte]
                    mods = get_modifiers(node)
                    exported = 'public' in mods
                    result.symbols.append(SymbolInfo(
                        name=class_name,
                        kind='class',
                        line=node.start_point[0] + 1,
                        exported=exported,
                    ))
                    # Visit body
                    body = node.child_by_field_name('body')
                    if body:
                        for child in body.children:
                            visit(child, class_name)
                return

            # Interface declaration
            if node.type == 'interface_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    interface_name = content[name_node.start_byte:name_node.end_byte]
                    mods = get_modifiers(node)
                    exported = 'public' in mods
                    result.symbols.append(SymbolInfo(
                        name=interface_name,
                        kind='interface',
                        line=node.start_point[0] + 1,
                        exported=exported,
                    ))
                return

            # Method declaration
            if node.type == 'method_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    method_name = content[name_node.start_byte:name_node.end_byte]
                    mods = get_modifiers(node)
                    exported = 'public' in mods or 'protected' in mods
                    params = self._extract_java_params(node, content)
                    result.symbols.append(SymbolInfo(
                        name=method_name,
                        kind='method',
                        line=node.start_point[0] + 1,
                        exported=exported,
                        parent=parent_class,
                        parameters=params,
                    ))
                return

            # Constructor
            if node.type == 'constructor_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    ctor_name = content[name_node.start_byte:name_node.end_byte]
                    mods = get_modifiers(node)
                    exported = 'public' in mods
                    params = self._extract_java_params(node, content)
                    result.symbols.append(SymbolInfo(
                        name=ctor_name,
                        kind='constructor',
                        line=node.start_point[0] + 1,
                        exported=exported,
                        parent=parent_class,
                        parameters=params,
                    ))
                return

            # Field declaration
            if node.type == 'field_declaration':
                declarator = None
                for child in node.children:
                    if child.type == 'variable_declarator':
                        declarator = child
                        break
                if declarator:
                    name_node = declarator.child_by_field_name('name')
                    if name_node:
                        field_name = content[name_node.start_byte:name_node.end_byte]
                        mods = get_modifiers(node)
                        exported = 'public' in mods
                        kind = 'constant' if 'final' in mods and 'static' in mods else 'variable'
                        result.symbols.append(SymbolInfo(
                            name=field_name,
                            kind=kind,
                            line=node.start_point[0] + 1,
                            exported=exported,
                            parent=parent_class,
                        ))
                return

            # Import declarations
            if node.type == 'import_declaration':
                import_text = content[node.start_byte:node.end_byte]
                result.imports.append(import_text)
                return

            # Recurse
            for child in node.children:
                visit(child, parent_class)

        visit(root)

    def _extract_java_params(self, func_node, content: str) -> List[str]:
        """Extract parameter names from Java method."""
        params = []
        params_node = func_node.child_by_field_name('parameters')
        if params_node:
            for child in params_node.children:
                if child.type == 'formal_parameter' or child.type == 'spread_parameter':
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        params.append(content[name_node.start_byte:name_node.end_byte])
        return params

    def extract_from_files(
        self,
        files: Dict[str, str],
        max_files: int = 30,
        max_file_size: int = 50000
    ) -> Dict[str, FileSymbols]:
        """Extract symbols from multiple files with limits.

        Args:
            files: Dict of {filepath: content}
            max_files: Maximum number of files to process
            max_file_size: Maximum file size to process (skip larger files)

        Returns:
            Dict of {filepath: FileSymbols}
        """
        results = {}
        processed = 0

        for filepath, content in files.items():
            if processed >= max_files:
                logger.debug(f"Reached max files limit ({max_files}), skipping remaining")
                break

            # Skip very large files
            if len(content) > max_file_size:
                logger.debug(f"Skipping {filepath}: too large ({len(content)} chars)")
                continue

            results[filepath] = self.extract_symbols(filepath, content)
            processed += 1

        return results

    def format_for_prompt(
        self,
        file_symbols: Dict[str, FileSymbols],
        max_symbols_per_file: int = 50,
        max_total_size: int = 15000
    ) -> str:
        """Format extracted symbols for inclusion in LLM prompt with size limit.

        Args:
            file_symbols: Dict of {filepath: FileSymbols}
            max_symbols_per_file: Max symbols to include per file
            max_total_size: Maximum total size of output

        Returns:
            Formatted string for prompt
        """
        if not file_symbols:
            return ""

        sections = ["## Symbol Table (for cross-file validation)\n"]
        sections.append("Use this to verify imports and API calls reference actually defined symbols.\n")
        current_size = 80  # Header size

        files_included = 0
        for filepath, symbols in file_symbols.items():
            if not symbols.symbols:
                continue

            if current_size >= max_total_size - 200:
                sections.append(f"\n... [{len(file_symbols) - files_included} more files not shown]")
                break

            file_section = [f"\n### {filepath}"]

            # Group by kind
            by_kind: Dict[str, List[SymbolInfo]] = {}
            for s in symbols.symbols[:max_symbols_per_file]:
                if s.kind not in by_kind:
                    by_kind[s.kind] = []
                by_kind[s.kind].append(s)

            for kind, syms in by_kind.items():
                if kind in ('class', 'interface'):
                    for s in syms[:10]:  # Limit classes/interfaces shown
                        export_mark = "+" if s.exported else "-"
                        file_section.append(f"  {export_mark} {kind} {s.name}")
                elif kind in ('function', 'method', 'constructor'):
                    for s in syms[:20]:  # Limit methods shown
                        export_mark = "+" if s.exported else "-"
                        params_str = ", ".join(s.parameters[:5]) if s.parameters else ""  # Limit params
                        if len(s.parameters) > 5:
                            params_str += ", ..."
                        parent_str = f"{s.parent}." if s.parent else ""
                        file_section.append(f"  {export_mark} {parent_str}{s.name}({params_str})")
                elif kind in ('variable', 'constant'):
                    names = [s.name for s in syms if s.exported][:15]  # Limit shown
                    if names:
                        file_section.append(f"  {kind}s: {', '.join(names)}")

            file_text = "\n".join(file_section)
            if current_size + len(file_text) > max_total_size:
                # Try to fit at least the file header
                if current_size + 50 < max_total_size:
                    sections.append(f"\n### {filepath} (truncated)")
                break

            sections.append(file_text)
            current_size += len(file_text)
            files_included += 1

        sections.append("\nLegend: + = exported/public, - = private/internal")

        return "\n".join(sections)

    def is_available(self) -> bool:
        """Check if tree-sitter is available."""
        return self._available


def get_symbol_extractor() -> SymbolExtractor:
    """Get a SymbolExtractor instance."""
    return SymbolExtractor()

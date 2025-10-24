"""Tests for naming consistency across packages."""

import ast
import pytest
from pathlib import Path


class TestNamingConsistency:
    """Tests for consistent naming patterns across packages."""
    
    def test_function_names_snake_case(self):
        """Test that all function names use snake_case."""
        packages = [
            "packages/gphotos-321sync-common/src/gphotos_321sync/common",
            "packages/gphotos-321sync-takeout-extractor/src/gphotos_321sync/takeout_extractor",
            "packages/gphotos-321sync-media-scanner/src/gphotos_321sync/media_scanner"
        ]
        
        violations = []
        
        for package_path in packages:
            package_dir = Path(package_path)
            if not package_dir.exists():
                continue
                
            for py_file in package_dir.rglob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                    
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            func_name = node.name
                            # Check for camelCase or PascalCase
                            if any(c.isupper() for c in func_name[1:]):
                                violations.append(f"{py_file}:{node.lineno}: {func_name}")
                                
                except (SyntaxError, UnicodeDecodeError):
                    # Skip files with syntax errors or encoding issues
                    continue
        
        if violations:
            pytest.fail(f"Found {len(violations)} naming violations:\n" + "\n".join(violations))
    
    def test_variable_names_snake_case(self):
        """Test that variable names use snake_case."""
        packages = [
            "packages/gphotos-321sync-common/src/gphotos_321sync/common",
            "packages/gphotos-321sync-takeout-extractor/src/gphotos_321sync/takeout_extractor",
            "packages/gphotos-321sync-media-scanner/src/gphotos_321sync/media_scanner"
        ]
        
        violations = []
        
        for package_path in packages:
            package_dir = Path(package_path)
            if not package_dir.exists():
                continue
                
            for py_file in package_dir.rglob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                    
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    var_name = target.id
                                    # Check for camelCase (but allow single words and constants)
                                    if (len(var_name) > 1 and 
                                        any(c.isupper() for c in var_name[1:]) and
                                        not var_name.isupper()):  # Exclude constants (UPPER_CASE)
                                        violations.append(f"{py_file}:{node.lineno}: {var_name}")
                                
                except (SyntaxError, UnicodeDecodeError):
                    # Skip files with syntax errors or encoding issues
                    continue
        
        if violations:
            pytest.fail(f"Found {len(violations)} variable naming violations:\n" + "\n".join(violations))
    
    def test_class_names_pascal_case(self):
        """Test that class names use PascalCase."""
        packages = [
            "packages/gphotos-321sync-common/src/gphotos_321sync/common",
            "packages/gphotos-321sync-takeout-extractor/src/gphotos_321sync/takeout_extractor",
            "packages/gphotos-321sync-media-scanner/src/gphotos_321sync/media_scanner"
        ]
        
        violations = []
        
        for package_path in packages:
            package_dir = Path(package_path)
            if not package_dir.exists():
                continue
                
            for py_file in package_dir.rglob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                    
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            class_name = node.name
                            # Check for snake_case in class names
                            if '_' in class_name:
                                violations.append(f"{py_file}:{node.lineno}: {class_name}")
                                
                except (SyntaxError, UnicodeDecodeError):
                    # Skip files with syntax errors or encoding issues
                    continue
        
        if violations:
            pytest.fail(f"Found {len(violations)} class naming violations:\n" + "\n".join(violations))

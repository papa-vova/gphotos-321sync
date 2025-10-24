"""Tests for type hint coverage across packages."""

import ast
import pytest
from pathlib import Path


class TestTypeHints:
    """Tests for type hint coverage."""
    
    def test_function_type_hints(self):
        """Test that all public functions have type hints."""
        packages = [
            "packages/gphotos-321sync-common/src/gphotos_321sync/common",
            "packages/gphotos-321sync-takeout-extractor/src/gphotos_321sync/takeout_extractor",
            "packages/gphotos-321sync-media-scanner/src/gphotos_321sync/media_scanner"
        ]
        
        missing_hints = []
        
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
                            # Skip private functions (starting with _)
                            if node.name.startswith('_'):
                                continue
                                
                            # Check if function has return type annotation
                            if node.returns is None:
                                missing_hints.append(f"{py_file}:{node.lineno}: {node.name}() missing return type")
                                
                            # Check if all parameters have type annotations (skip 'self' and 'cls')
                            for arg in node.args.args:
                                if arg.annotation is None and arg.arg not in ('self', 'cls'):
                                    missing_hints.append(f"{py_file}:{node.lineno}: {node.name}({arg.arg}) missing type hint")
                                
                except (SyntaxError, UnicodeDecodeError):
                    # Skip files with syntax errors or encoding issues
                    continue
        
        if missing_hints:
            pytest.fail(f"Found {len(missing_hints)} missing type hints:\n" + "\n".join(missing_hints[:20]))  # Show first 20
    
    def test_class_method_type_hints(self):
        """Test that all public class methods have type hints."""
        packages = [
            "packages/gphotos-321sync-common/src/gphotos_321sync/common",
            "packages/gphotos-321sync-takeout-extractor/src/gphotos_321sync/takeout_extractor",
            "packages/gphotos-321sync-media-scanner/src/gphotos_321sync/media_scanner"
        ]
        
        missing_hints = []
        
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
                            for method in node.body:
                                if isinstance(method, ast.FunctionDef):
                                    # Skip private methods (starting with _)
                                    if method.name.startswith('_'):
                                        continue
                                        
                                    # Check if method has return type annotation
                                    if method.returns is None:
                                        missing_hints.append(f"{py_file}:{method.lineno}: {node.name}.{method.name}() missing return type")
                                        
                                    # Check if all parameters have type annotations (skip 'self' and 'cls')
                                    for arg in method.args.args:
                                        if arg.annotation is None and arg.arg not in ('self', 'cls'):
                                            missing_hints.append(f"{py_file}:{method.lineno}: {node.name}.{method.name}({arg.arg}) missing type hint")
                                
                except (SyntaxError, UnicodeDecodeError):
                    # Skip files with syntax errors or encoding issues
                    continue
        
        if missing_hints:
            pytest.fail(f"Found {len(missing_hints)} missing type hints:\n" + "\n".join(missing_hints[:20]))  # Show first 20

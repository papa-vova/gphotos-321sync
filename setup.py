"""Setup script for gphotos-sync."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="gphotos-sync",
    version="0.1.0",
    description="Google Photos Takeout backup and synchronization tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/gphotos-321sync",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "sqlalchemy>=2.0.0",
        "alembic>=1.12.0",
        "aiofiles>=23.2.0",
        "platformdirs>=4.0.0",
        "toml>=0.10.2",
        "pillow>=10.1.0",
        "piexif>=1.1.3",
        "py7zr>=0.20.0",
        "python-multipart>=0.0.6",
        "psutil>=5.9.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.11.0",
            "ruff>=0.1.6",
            "mypy>=1.7.0",
        ],
        "cloud": [
            "boto3>=1.29.0",
            "celery>=5.3.0",
            "redis>=5.0.0",
            "psycopg2-binary>=2.9.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "gphotos-sync=gphotos_sync.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="google-photos backup sync takeout",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/gphotos-321sync/issues",
        "Source": "https://github.com/yourusername/gphotos-321sync",
    },
)

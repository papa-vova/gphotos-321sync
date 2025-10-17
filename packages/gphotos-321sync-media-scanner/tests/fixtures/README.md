# Test Fixtures

This directory contains scripts for creating test data samples for end-to-end testing.

## Scripts

### `sample_test_data.py`

Creates a representative stratified sample from a file list.

**Usage:**

```bash
python sample_test_data.py <input_file_list> <output_sample_list> [--sample-rate 0.3]
```

**Example:**

```bash
# Create a 30% sample from your file list
python sample_test_data.py input_files.txt sample_files.txt --sample-rate 0.3
```

**Features:**

- Stratified sampling across albums (directories)
- Maintains media + sidecar pairs
- Includes album metadata.json files
- Reproducible (uses random seed)

### `copy_test_data.py`

Copies sampled files to a test directory, preserving structure.

**Usage:**

```bash
python copy_test_data.py <sample_file_list> <source_root> <dest_root>
```

**Example:**

```bash
# Copy sampled files to test directory
python copy_test_data.py sample_files.txt /path/to/Takeout ./test_data

# Dry run to see what would be copied
python copy_test_data.py sample_files.txt /path/to/Takeout ./test_data --dry-run
```

## Workflow

1. **Generate file list** from your source data:

   ```bash
   # On Windows (PowerShell)
   Get-ChildItem -Recurse -File | Select-Object -ExpandProperty FullName > file_list.txt
   
   # On Linux/Mac
   find /path/to/Takeout -type f > file_list.txt
   ```

2. **Create sample**:

   ```bash
   python sample_test_data.py file_list.txt sample_files.txt --sample-rate 0.3
   ```

3. **Copy files**:

   ```bash
   python copy_test_data.py sample_files.txt /path/to/Takeout ./test_data
   ```

4. **Run tests** on the test data directory

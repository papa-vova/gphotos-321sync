# Complete Project Refactoring Plan

## Phase 1: Low Priority Items (Documentation & Naming)

### Step 1.1: Create New Test Structure
- [x] Create `tests/` folder with package-specific subfolders
- [x] Structure:
  ```
  tests/
  ├── common/
  │   ├── test_path_utils.py
  │   ├── test_logging_config.py
  │   └── test_checksums.py
  ├── takeout_extractor/
  │   ├── test_extractor.py
  │   ├── test_config.py
  │   └── test_verification.py
  └── media_scanner/
      ├── test_discovery.py
      ├── test_file_processor.py
      └── test_parallel_scanner.py
  ```

### Step 1.2: Add Missing Constants
- [x] Replace magic numbers with named constants
- [x] Files: 
  - `packages/gphotos-321sync-media-scanner/src/gphotos_321sync/media_scanner/file_processor.py`
  - `packages/gphotos-321sync-common/src/gphotos_321sync/common/checksums.py`
- [x] Action: Add `CRC32_CHUNK_SIZE = 64 * 1024` constant
- [x] Test: Create `tests/common/test_checksums.py` to verify constants

### Step 1.3: Improve Variable Naming
- [x] Fix inconsistent naming patterns
- [x] Files: All packages
- [x] Action: Standardize function parameter names (snake_case consistency)
- [x] Test: Create naming consistency tests

### Step 1.4: Add Missing Type Hints
- [x] Add type hints to functions missing them
- [x] Files: All packages
- [x] Action: Add `-> Optional[Dict[str, Any]]` type hints where missing
- [x] Test: Create `tests/common/test_type_hints.py` to verify type coverage
- [x] Added ALL missing type hints (reduced from 24 to 0 missing - 100% complete)

## Phase 2: Medium Priority Items (Code Structure)

### Step 2.1: Consolidate CRC32 Functions
- [ ] Remove duplication between common and media-scanner
- [ ] Files: 
  - `packages/gphotos-321sync-common/src/gphotos_321sync/common/checksums.py`
  - `packages/gphotos-321sync-media-scanner/src/gphotos_321sync/media_scanner/file_processor.py`
- [ ] Action: 
  - Keep only `compute_crc32()` in common package
  - Remove `calculate_crc32()` from media-scanner
  - Update imports in media-scanner
- [ ] Test: Create `tests/common/test_checksums.py` to verify CRC32 calculation

### Step 2.2: Standardize Error Handling
- [ ] Choose one error handling pattern (dict vs exceptions)
- [ ] Files: All packages
- [ ] Action: Standardize on exception-based error handling
- [ ] Test: Create `tests/common/test_error_handling.py` to verify consistency

### Step 2.3: Extract Complex Logic
- [ ] Break down complex functions into smaller ones
- [ ] Files: 
  - `packages/gphotos-321sync-media-scanner/src/gphotos_321sync/media_scanner/parallel_scanner_helpers.py`
- [ ] Action: Split `match_orphaned_sidecars()` into smaller functions
- [ ] Test: Create `tests/media_scanner/test_parallel_scanner_helpers.py`

## Phase 3: High Priority Items (Critical Issues)

### Step 3.1: Refactor `discover_files()` Function
- [ ] Split 500+ line function into manageable pieces
- [ ] Files: 
  - `packages/gphotos-321sync-media-scanner/src/gphotos_321sync/media_scanner/discovery.py`
- [ ] Action: 
  - Extract `_collect_media_files()` - file collection logic
  - Extract `_create_file_info()` - FileInfo creation logic
  - Extract `_match_sidecar_patterns()` - sidecar matching logic
  - Keep main `discover_files()` as orchestrator
- [ ] Test: Create `tests/media_scanner/test_discovery.py` with comprehensive scenarios

### Step 3.2: Simplify Sidecar Matching Logic
- [ ] Refactor complex sidecar matching heuristics
- [ ] Files: 
  - `packages/gphotos-321sync-media-scanner/src/gphotos_321sync/media_scanner/discovery.py` (lines 170-450)
- [ ] Action: 
  - Extract `_match_sidecar_to_media()` function
  - Extract `_handle_truncated_sidecars()` function
  - Extract `_handle_duplicate_suffixes()` function
- [ ] Test: Create `tests/media_scanner/test_sidecar_matching.py`

### Step 3.3: Optimize E2E Test Performance
- [ ] Make E2E tests faster and more maintainable
- [ ] Files: 
  - `packages/gphotos-321sync-media-scanner/tests/e2e/generate_test_data.py`
- [ ] Action: 
  - Add `--fast-mode` option for smaller test datasets
  - Create separate fast/slow test categories
  - Add test data caching
- [ ] Test: Create `tests/media_scanner/test_e2e_fast.py`

## Implementation Strategy

### Phase 1: Low Priority (Week 1)
1. **Day 1**: Create new test structure
2. **Day 2**: Add constants and improve naming
3. **Day 3**: Add missing type hints
4. **Day 4**: Test and verify Phase 1 changes
5. **Day 5**: Create comprehensive test coverage

### Phase 2: Medium Priority (Week 2)
1. **Day 1**: Consolidate CRC32 functions
2. **Day 2**: Standardize error handling
3. **Day 3**: Extract complex logic
4. **Day 4**: Test and verify Phase 2 changes
5. **Day 5**: Create integration tests

### Phase 3: High Priority (Week 3)
1. **Day 1-2**: Refactor `discover_files()` function
2. **Day 3-4**: Simplify sidecar matching logic
3. **Day 5-6**: Optimize E2E test performance
4. **Day 7**: Final testing and verification

## Testing Strategy

### After Each Step:
1. **Unit Tests**: Run new test suite
2. **Integration Tests**: Test affected functionality
3. **Linting**: Run linters to catch issues
4. **Manual Testing**: Verify core functionality works

### After Each Phase:
1. **Full Test Suite**: Run all new tests
2. **Performance Testing**: Verify no performance regressions
3. **Code Review**: Review changes for quality
4. **Documentation**: Update any changed interfaces

## Success Criteria

### Phase 1 Complete When:
- New test structure created
- All magic numbers replaced with constants
- Consistent naming across all packages
- Type hints added to all functions
- Comprehensive test coverage for low priority items

### Phase 2 Complete When:
- No code duplication between packages
- Consistent error handling patterns
- Complex functions broken into smaller pieces
- Integration tests passing

### Phase 3 Complete When:
- `discover_files()` function <100 lines
- Sidecar matching logic <50 lines per function
- E2E tests run in <30 seconds
- All critical issues resolved

## Risk Mitigation

### Backup Strategy:
- Create git branch before each phase
- Commit after each step
- Keep rollback plan ready

### Testing Strategy:
- Run tests after each step
- Verify functionality before moving to next step
- Keep old tests in `tests_obsolete` folder

### Documentation:
- Document each change in commit messages
- Update README if interfaces change
- Keep change log of refactoring steps

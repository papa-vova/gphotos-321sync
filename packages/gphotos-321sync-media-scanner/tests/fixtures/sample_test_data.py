"""
Script to create a representative sample of test data from a file list.

This script reads a list of file paths and creates a stratified sample
for end-to-end testing. The sample is representative across:
- Different albums (directories)
- File types (images, videos, JSON sidecars)
- File naming patterns

Usage:
    python sample_test_data.py <input_file_list> <output_sample_list> [--sample-rate 0.3]

Example:
    python sample_test_data.py file_list.txt sample_files.txt --sample-rate 0.3
"""

import argparse
import random
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Set


def parse_file_list(file_path: str) -> List[str]:
    """
    Read file list from input file.
    
    Args:
        file_path: Path to file containing list of files (one per line)
        
    Returns:
        List of file paths
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def categorize_files(file_paths: List[str]) -> Dict[str, Dict[str, List[str]]]:
    """
    Categorize files by album (directory) and type.
    
    Args:
        file_paths: List of file paths
        
    Returns:
        Dictionary: {album_path: {file_type: [files]}}
    """
    albums = defaultdict(lambda: defaultdict(list))
    
    for file_path in file_paths:
        path = Path(file_path)
        
        # Get album (parent directory)
        album = str(path.parent)
        
        # Categorize by file type
        suffix = path.suffix.lower()
        if suffix in ['.jpg', '.jpeg', '.png', '.heic', '.gif', '.bmp', '.webp']:
            file_type = 'image'
        elif suffix in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
            file_type = 'video'
        elif suffix == '.json':
            file_type = 'json'
        else:
            file_type = 'other'
        
        albums[album][file_type].append(file_path)
    
    return albums


def stratified_sample(
    albums: Dict[str, Dict[str, List[str]]],
    sample_rate: float = 0.3
) -> List[str]:
    """
    Create a stratified sample across albums and file types.
    
    Ensures representation from:
    - All albums (or at least 30% of albums if there are many)
    - All file types within each album
    - Maintains media + sidecar pairs
    
    Args:
        albums: Categorized files by album and type
        sample_rate: Proportion of files to sample (default: 0.3 = 30%)
        
    Returns:
        List of sampled file paths
    """
    sampled_files = []
    
    # Determine which albums to include
    album_list = list(albums.keys())
    num_albums_to_sample = max(1, int(len(album_list) * sample_rate))
    
    # If there are many albums, sample albums too
    if len(album_list) > 10:
        sampled_albums = random.sample(album_list, num_albums_to_sample)
    else:
        # Include all albums if there are few
        sampled_albums = album_list
    
    # Sample files from each selected album
    for album in sampled_albums:
        file_types = albums[album]
        
        # Sample media files (images and videos)
        for media_type in ['image', 'video']:
            if media_type in file_types:
                media_files = file_types[media_type]
                num_to_sample = max(1, int(len(media_files) * sample_rate))
                sampled_media = random.sample(media_files, num_to_sample)
                
                # Add sampled media files
                sampled_files.extend(sampled_media)
                
                # Add corresponding JSON sidecars if they exist
                for media_file in sampled_media:
                    # Check for various sidecar patterns
                    sidecar_patterns = [
                        f"{media_file}.json",
                        f"{media_file}.supplemental-metadata.json",
                        f"{media_file}.supplemental-me.json",
                    ]
                    
                    if 'json' in file_types:
                        for sidecar in sidecar_patterns:
                            if sidecar in file_types['json']:
                                sampled_files.append(sidecar)
        
        # Always include album metadata.json if it exists
        if 'json' in file_types:
            for json_file in file_types['json']:
                if Path(json_file).name == 'metadata.json':
                    sampled_files.append(json_file)
    
    return sorted(set(sampled_files))  # Remove duplicates and sort


def write_sample_list(file_paths: List[str], output_path: str):
    """
    Write sampled file list to output file.
    
    Args:
        file_paths: List of file paths to write
        output_path: Output file path
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for file_path in file_paths:
            f.write(f"{file_path}\n")


def print_statistics(
    original_files: List[str],
    sampled_files: List[str],
    albums: Dict[str, Dict[str, List[str]]]
):
    """
    Print sampling statistics.
    
    Args:
        original_files: Original file list
        sampled_files: Sampled file list
        albums: Categorized albums
    """
    print("\n" + "=" * 70)
    print("SAMPLING STATISTICS")
    print("=" * 70)
    
    print(f"\nOriginal files:     {len(original_files):>8,}")
    print(f"Sampled files:      {len(sampled_files):>8,}")
    print(f"Sample rate:        {len(sampled_files)/len(original_files)*100:>7.1f}%")
    
    print(f"\nOriginal albums:    {len(albums):>8,}")
    sampled_albums = len(set(Path(f).parent for f in sampled_files))
    print(f"Sampled albums:     {sampled_albums:>8,}")
    print(f"Album coverage:     {sampled_albums/len(albums)*100:>7.1f}%")
    
    # Count file types in sample
    image_count = sum(1 for f in sampled_files if Path(f).suffix.lower() in ['.jpg', '.jpeg', '.png', '.heic'])
    video_count = sum(1 for f in sampled_files if Path(f).suffix.lower() in ['.mp4', '.mov'])
    json_count = sum(1 for f in sampled_files if Path(f).suffix.lower() == '.json')
    
    print(f"\nSample composition:")
    print(f"  Images:           {image_count:>8,}")
    print(f"  Videos:           {video_count:>8,}")
    print(f"  JSON sidecars:    {json_count:>8,}")
    print(f"  Other:            {len(sampled_files) - image_count - video_count - json_count:>8,}")
    
    print("\n" + "=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Create a representative sample of test data from a file list'
    )
    parser.add_argument(
        'input_file',
        help='Input file containing list of files (one per line)'
    )
    parser.add_argument(
        'output_file',
        help='Output file for sampled file list'
    )
    parser.add_argument(
        '--sample-rate',
        type=float,
        default=0.3,
        help='Sample rate (0.0-1.0, default: 0.3 = 30%%)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)'
    )
    
    args = parser.parse_args()
    
    # Validate sample rate
    if not 0.0 < args.sample_rate <= 1.0:
        parser.error("Sample rate must be between 0.0 and 1.0")
    
    # Set random seed for reproducibility
    random.seed(args.seed)
    
    print(f"Reading file list from: {args.input_file}")
    original_files = parse_file_list(args.input_file)
    
    print(f"Categorizing {len(original_files):,} files...")
    albums = categorize_files(original_files)
    
    print(f"Creating stratified sample (rate: {args.sample_rate:.1%})...")
    sampled_files = stratified_sample(albums, args.sample_rate)
    
    print(f"Writing sample to: {args.output_file}")
    write_sample_list(sampled_files, args.output_file)
    
    print_statistics(original_files, sampled_files, albums)
    
    print(f"\n✅ Sample created successfully!")
    print(f"   Use this file list to copy files for testing.")


if __name__ == '__main__':
    main()

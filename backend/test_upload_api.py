#!/usr/bin/env python3
"""
Test script for Voice EMR Audio Upload APIs
Demonstrates both single and bulk upload functionality
"""

import requests
import json
from pathlib import Path

# API Configuration
BASE_URL = "http://localhost:8000"

def test_api_info():
    """Get API information and capabilities"""
    print("=" * 60)
    print("1. Testing API Info Endpoint")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    print()

def test_health_check():
    """Check system health"""
    print("=" * 60)
    print("2. Testing Health Check")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    print()

def test_single_upload(audio_file_path):
    """Test single audio file upload"""
    print("=" * 60)
    print("3. Testing Single File Upload")
    print("=" * 60)
    
    if not Path(audio_file_path).exists():
        print(f"Error: File not found: {audio_file_path}")
        return None
    
    with open(audio_file_path, 'rb') as f:
        files = {'audio': f}
        data = {
            'patient_id': 'P001',
            'clinician': 'Dr. Smith'
        }
        
        response = requests.post(
            f"{BASE_URL}/upload-consultation-audio",
            files=files,
            data=data
        )
    
    print(f"Status: {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2))
    print()
    
    if response.status_code == 200:
        return result.get('audio_id')
    return None

def test_bulk_upload(audio_file_paths):
    """Test bulk audio file upload"""
    print("=" * 60)
    print("4. Testing Bulk File Upload")
    print("=" * 60)
    
    files = []
    for path in audio_file_paths:
        if not Path(path).exists():
            print(f"Warning: File not found: {path}")
            continue
        files.append(('audio_files', open(path, 'rb')))
    
    if not files:
        print("Error: No valid files to upload")
        return []
    
    try:
        data = {
            'patient_id': 'P002',
            'clinician': 'Dr. Johnson'
        }
        
        response = requests.post(
            f"{BASE_URL}/upload-consultation-audio-bulk",
            files=files,
            data=data
        )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        print(json.dumps(result, indent=2))
        print()
        
        # Extract audio IDs from successful uploads
        audio_ids = [
            r['audio_id'] for r in result.get('results', [])
            if r['status'] == 'accepted'
        ]
        return audio_ids
        
    finally:
        # Close all file handles
        for _, f in files:
            f.close()

def test_single_status(audio_id):
    """Check status of a single audio file"""
    print("=" * 60)
    print(f"5. Testing Single Status Check (audio_id={audio_id})")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/consultation-status/{audio_id}")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    print()

def test_batch_status(audio_ids):
    """Check status of multiple audio files"""
    print("=" * 60)
    print(f"6. Testing Batch Status Check ({len(audio_ids)} files)")
    print("=" * 60)
    
    response = requests.post(
        f"{BASE_URL}/consultation-status-batch",
        json=audio_ids
    )
    
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    print()

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("VOICE EMR API TEST SUITE")
    print("=" * 60 + "\n")
    
    # Test 1: API Info
    test_api_info()
    
    # Test 2: Health Check
    test_health_check()
    
    # Example usage - replace with your actual audio file paths
    print("=" * 60)
    print("NOTE: Update file paths below with your actual audio files")
    print("=" * 60)
    print()
    
    # Example single upload
    single_audio_file = "path/to/consultation1.wav"
    # audio_id = test_single_upload(single_audio_file)
    
    # Example bulk upload
    bulk_audio_files = [
        "path/to/consultation1.wav",
        "path/to/consultation2.wav",
        "path/to/consultation3.wav"
    ]
    # audio_ids = test_bulk_upload(bulk_audio_files)
    
    # Example status checks
    # if audio_id:
    #     test_single_status(audio_id)
    
    # if audio_ids:
    #     test_batch_status(audio_ids)
    
    print("\n" + "=" * 60)
    print("TESTS COMPLETED")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()

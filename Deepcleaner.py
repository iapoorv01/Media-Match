import os
import imagehash
from PIL import Image
import subprocess
import cv2

# Function to generate hash of an image
def get_image_hash(image_path):
    try:
        img = Image.open(image_path)
        return imagehash.phash(img)
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None

# Function to generate a hash from the first frame of a video
def get_video_hash(video_path):
    try:
        # Open the video using OpenCV
        video = cv2.VideoCapture(video_path)
        ret, frame = video.read()
        if not ret:
            print(f"Could not read frame from video: {video_path}")
            return None
        # Convert the frame to grayscale and then hash it
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        pil_image = Image.fromarray(gray)
        return imagehash.phash(pil_image)
    except Exception as e:
        print(f"Error processing video {video_path}: {e}")
        return None

# Function to compare two hashes (image or video)
def compare_files(file1, file2):
    hash1 = get_file_hash(file1)
    hash2 = get_file_hash(file2)
    if hash1 is None or hash2 is None:
        return False
    return hash1 - hash2  # This gives a distance; lower means more similar

# Function to return the hash of a file (image or video)
def get_file_hash(file_path):
    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
        return get_image_hash(file_path)
    elif file_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.flv')):
        return get_video_hash(file_path)
    else:
        return None

# Function to process files and delete duplicates
def process_files():
    file_paths = []
    duplicates = []

    # Start from the root directory to scan the whole system (C:\ for Windows)
    root_dir = 'C:\\'  # Change this to '/' for Linux or macOS
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            file_path = os.path.join(root, file)
            # Scan for both image and video files
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.mp4', '.avi', '.mov', '.mkv', '.flv')):
                file_paths.append(file_path)

    print(f"Found {len(file_paths)} files to process.")

    hashes = {}

    for path in file_paths:
        file_hash = get_file_hash(path)
        if file_hash is None:
            continue  # Skip files that couldn't be processed

        if file_hash in hashes:
            print(f"Duplicate found: {path} and {hashes[file_hash]}")
            # Ask user if they want to delete
            delete = input(f"Do you want to delete {path}? (y/n): ")
            if delete.lower() == 'y':
                try:
                    os.remove(path)
                    print(f"Deleted {path}")
                except Exception as e:
                    print(f"Failed to delete {path}: {e}")
        else:
            hashes[file_hash] = path

    print(f"Successfully processed {len(hashes)} unique files.")

# Main function to start the process
def main():
    # Ask user for permission to scan and modify files
    permission = input("Do you want to scan the whole system and delete duplicate images and videos? (yes/no): ").lower()

    if permission == 'yes':
        # Skip granting permissions if not needed
        grant_permission = input("Do you want to modify file permissions and access all files in the system? (yes/no): ").lower()

        if grant_permission == 'yes':
            print("Skipping permission modification due to system limitations.")
            # You can also opt to grant permissions manually if needed

        # Start processing files (images and videos)
        process_files()
    else:
        print("Operation canceled.")

if __name__ == "__main__":
    main()

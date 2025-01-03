import os
import imagehash
from PIL import Image
import subprocess
import cv2
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
import hashlib
import shutil
import numpy as np
from tensorflow.keras.applications import VGG16
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.vgg16 import preprocess_input
from sklearn.metrics.pairwise import cosine_similarity

# Setup logging
logging.basicConfig(filename='duplicate_finder.log', level=logging.DEBUG, format='%(asctime)s - %(message)s')

# Global variables
popup_active = False
abort_scan = False
scan_event = threading.Event()  # Event to control the scanner's waiting state
executor = ThreadPoolExecutor(max_workers=4)  # Executor for parallel processing
progress_bar = None

# Backup folder path
BACKUP_DIR = r"C:\Backup"

# Load pre-trained VGG16 model for feature extraction
model = VGG16(weights='imagenet', include_top=False, input_shape=(224, 224, 3))


# Function to ask the user if they want to back up the duplicate file
def ask_backup(path):
    return messagebox.askyesno("Backup Confirmation", f"Do you want to back up the duplicate file: {path}?")


# Function to ask the user if they want to delete backups after scan
def ask_delete_backups():
    return messagebox.askyesno("Delete Backups", "Do you want to delete all backup files after scan?")


# Function to create a backup of a file
def backup_file(file_path):
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    try:
        # Create a backup by copying the file to the backup directory
        backup_path = os.path.join(BACKUP_DIR, os.path.basename(file_path))
        shutil.copy(file_path, backup_path)
        logging.info(f"Backed up file: {file_path} to {backup_path}")
    except Exception as e:
        logging.error(f"Error while backing up {file_path}: {e}")


# Function to delete all backup files in the backup directory
def delete_backups():
    try:
        # Loop through and delete all files in the backup directory
        for filename in os.listdir(BACKUP_DIR):
            file_path = os.path.join(BACKUP_DIR, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                logging.info(f"Deleted backup file: {file_path}")
    except Exception as e:
        logging.error(f"Error while deleting backup files: {e}")


# Function to extract features from an image using VGG16
def extract_image_features(image_path):
    try:
        img = Image.open(image_path)
        img = img.resize((224, 224))  # Resize to VGG16 input size
        img_array = np.array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = preprocess_input(img_array)
        features = model.predict(img_array)
        return features.flatten()  # Flatten the features to a 1D array
    except Exception as e:
        logging.error(f"Error processing {image_path}: {e}")
        return None


# Function to extract features from a video by sampling frames using VGG16
def extract_video_features(video_path):
    try:
        video = cv2.VideoCapture(video_path)
        frames_to_sample = 5  # Sample 5 frames at regular intervals
        features = []
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        interval = total_frames // frames_to_sample
        for i in range(0, total_frames, interval):
            video.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = video.read()
            if not ret:
                logging.warning(f"Could not read frame at position {i}")
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            pil_image = Image.fromarray(gray)
            frame_features = extract_image_features(pil_image)
            if frame_features is not None:
                features.append(frame_features)
        video.release()
        return features
    except Exception as e:
        logging.error(f"Error processing video {video_path}: {e}")
        return None


# Function to compare two images or videos based on their features
def compare_features(features1, features2):
    return cosine_similarity([features1], [features2])[0][0]  # Similarity score between 0 and 1


# Function to get AI-powered features from a file (image or video)
def get_file_features(file_path):
    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):  # Image formats
        return extract_image_features(file_path)
    elif file_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.flv')):  # Video formats
        return extract_video_features(file_path)
    else:
        return None


# Function to process files and delete duplicates
def process_files(progress_callback, result_callback):
    global abort_scan
    file_paths = []
    features_dict = {}

    excluded_dirs = [
        r"Program Files", r"Windows", r"AppData", r"ProgramData", r"C:\Users\Lenovo\anaconda3",
        r"C:\Users\Lenovo\.vscode",
        r"Intel", r"DRIVER", r"Program Files (x86)", r"Users\Public", r"System Volume Information"
    ]

    for root, dirs, files in os.walk("C:\\"):
        if any(excluded in root for excluded in excluded_dirs):
            continue
        for file in files:
            file_path = os.path.join(root, file)
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.mp4', '.avi', '.mov', '.mkv', '.flv')):
                file_paths.append(file_path)

    progress_callback(f"Found {len(file_paths)} files to process.")
    update_status_bar("Scanning files...")  # Update status bar for the scanning process

    for path in file_paths:
        if abort_scan:
            break  # If aborted, stop processing

        file_features = get_file_features(path)
        if file_features is None:
            continue

        duplicate_found = False
        for existing_file, existing_features in features_dict.items():
            similarity = compare_features(file_features, existing_features)
            if similarity > 0.9:  # If similarity is greater than 90%, flag as duplicate
                progress_callback(f"Duplicate found: {path} and {existing_file}")

                # Ask user if they want to back up the duplicate file before deletion
                if ask_backup(path):
                    backup_file(path)

                # Ask if they want to delete the duplicate file
                progress_callback(f"Do you want to delete {path}? (y/n)")

                # Show custom popup window for user input to confirm deletion
                show_deletion_popup(path, existing_file)

                # Wait for the user to interact with the popup before proceeding
                scan_event.wait()  # Wait until the event is set by popup action (delete/skip)

                # Reset event for next pop-up
                scan_event.clear()
                duplicate_found = True
                break

        if not duplicate_found:
            features_dict[path] = file_features  # Store the file features if no duplicate found

    # Ask if the user wants to delete backups after all processing
    if ask_delete_backups():
        delete_backups()

    if abort_scan:
        result_callback("Scan aborted.")
    else:
        result_callback(f"Successfully processed {len(features_dict)} unique files.")
        update_status_bar("Scan completed.")  # Update status bar when scan finishes


# Custom Popup Window for Deletion
def show_deletion_popup(path, original_path):
    global popup_active
    if popup_active:
        return  # Prevent opening another pop-up if one is already open

    # Set the flag to indicate a popup is active
    popup_active = True
    window.after(0, create_popup, path, original_path)  # Ensure popup runs in the main thread


def create_popup(path, original_path):
    popup = tk.Toplevel()
    popup.title("Confirm Deletion")

    label = tk.Label(popup, text=f"Duplicate found: {path}\nOriginal: {original_path}\nDo you want to delete it?",
                     font=("Helvetica", 12), bg="#f0f0f0")
    label.pack(pady=10)

    def delete_action():
        try:
            os.remove(path)
            logging.info(f"Deleted {path}")
        except Exception as e:
            logging.error(f"Failed to delete {path}: {e}")
        finally:
            popup.destroy()  # Close the popup after action
            set_popup_inactive()
            scan_event.set()  # Signal that the popup interaction is complete

    def skip_action():
        popup.destroy()  # Close the popup and skip deletion
        set_popup_inactive()
        scan_event.set()  # Signal that the popup interaction is complete

    delete_button = tk.Button(popup, text="Delete", command=delete_action, bg="#ff6347", fg="white",
                              font=("Helvetica", 12), relief="flat", bd=2)
    delete_button.pack(pady=5, padx=10)

    skip_button = tk.Button(popup, text="Skip", command=skip_action, bg="#32cd32", fg="white", font=("Helvetica", 12),
                            relief="flat", bd=2)
    skip_button.pack(pady=5, padx=10)

    # Keep the popup responsive
    popup.transient()  # Popup will not block interaction with parent
    popup.grab_set()  # Ensure the popup is modal
    popup.mainloop()


# Set the flag back to False when the popup is closed
def set_popup_inactive():
    global popup_active
    popup_active = False


# GUI Updates and Callbacks
def start_processing():
    update_status_bar("Scanning...")  # Update status bar as soon as scan starts
    progress_bar.start()  # Start the progress bar
    threading.Thread(target=run_processing, daemon=True).start()


def run_processing():
    process_files(update_progress, show_result)


def update_progress(message):
    progress_text.insert(tk.END, message + "\n")
    progress_text.yview(tk.END)
    update_status_bar(message)


def show_result(message):
    progress_text.insert(tk.END, message + "\n")
    progress_text.yview(tk.END)
    update_status_bar("Process completed")
    messagebox.showinfo("Process Completed", message)


def abort_scan_process():
    global abort_scan
    abort_scan = True
    progress_text.insert(tk.END, "Aborting scan...\n")
    progress_text.yview(tk.END)
    update_status_bar("Scan aborted")
    progress_bar.stop()  # Stop progress bar


def update_status_bar(message):
    status_bar.config(text=message)


# Setup the GUI
def setup_gui():
    global window, progress_text, progress_bar, status_bar

    window = tk.Tk()
    window.title("AI-Powered Duplicate Finder")
    window.geometry("700x600")

    # Create and configure the status bar
    status_bar = tk.Label(window, text="Ready", anchor="w", relief="sunken", height=2)
    status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # Create and configure the progress bar
    progress_bar = ttk.Progressbar(window, orient="horizontal", length=400, mode="indeterminate")
    progress_bar.pack(pady=10)

    # Create and configure the start button
    start_button = tk.Button(window, text="Start Scan", command=start_processing, bg="#32cd32", fg="white",
                             font=("Helvetica", 12))
    start_button.pack(pady=10)

    # Tooltip for Start Scan button
    start_button.tooltip = create_tooltip(start_button, "Click to start scanning for duplicates.")

    # Create and configure the abort button
    abort_button = tk.Button(window, text="Abort Scan", command=abort_scan_process, bg="#ff6347", fg="white",
                             font=("Helvetica", 12))
    abort_button.pack(pady=10)

    # Tooltip for Abort button
    abort_button.tooltip = create_tooltip(abort_button, "Click to abort the scan process.")

    # Create a text box for progress messages
    progress_text = tk.Text(window, height=15, width=80, font=("Helvetica", 10), wrap=tk.WORD)
    progress_text.pack(pady=10)

    window.mainloop()


def create_tooltip(widget, text):
    tooltip = tk.Label(window, text=text, bg="yellow", relief="solid", bd=1, font=("Helvetica", 10))
    tooltip.place_forget()  # Hide initially

    def on_enter(event):
        tooltip.place(x=widget.winfo_x(), y=widget.winfo_y() - 30)

    def on_leave(event):
        tooltip.place_forget()

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)
    return tooltip


# Start the GUI
setup_gui()

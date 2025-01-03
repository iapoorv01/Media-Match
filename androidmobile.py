import os
import imagehash
from PIL import Image
import cv2
import threading
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

# Global variables
popup_active = False
abort_scan = False
scan_event = threading.Event()  # Event to control the scanner's waiting state
progress_text = None  # To reference progress text

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

# Function to return the hash of a file (image or video)
def get_file_hash(file_path):
    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
        return get_image_hash(file_path)
    elif file_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.flv')):
        return get_video_hash(file_path)
    else:
        return None

# Function to process files and delete duplicates
def process_files(progress_callback, result_callback):
    global abort_scan
    file_paths = []
    hashes = {}

    excluded_dirs = [
        r"Program Files", r"Windows", r"AppData", r"ProgramData", r"C:\Users\Lenovo\anaconda3", r"C:\Users\Lenovo\.vscode",
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

    for path in file_paths:
        if abort_scan:
            break  # If aborted, stop processing

        file_hash = get_file_hash(path)
        if file_hash is None:
            continue

        if file_hash in hashes:
            progress_callback(f"Duplicate found: {path} and {hashes[file_hash]}")
            progress_callback(f"Do you want to delete {path}? (y/n)")

            # Show custom popup window for user input to confirm deletion
            show_deletion_popup(path, hashes[file_hash])

            # Wait for the user to interact with the popup before proceeding
            scan_event.wait()  # Wait until the event is set by popup action (delete/skip)

            # Reset event for next pop-up
            scan_event.clear()
        else:
            hashes[file_hash] = path

        # Check abort scan flag frequently during processing
        if abort_scan:
            progress_callback("Scan aborted.")
            break  # Exit the loop early if abort flag is set

    if not abort_scan:
        result_callback(f"Successfully processed {len(hashes)} unique files.")

# Custom Popup Window for Deletion
def show_deletion_popup(path, original_path):
    global popup_active
    if popup_active:
        return  # Prevent opening another pop-up if one is already open

    # Set the flag to indicate a popup is active
    popup_active = True
    window.after(0, create_popup, path, original_path)  # Ensure popup runs in the main thread

def create_popup(path, original_path):
    # Create Kivy popup window for deletion confirmation
    layout = BoxLayout(orientation='vertical')
    label = Label(text=f"Duplicate found: {path}\nOriginal: {original_path}\nDo you want to delete it?")
    layout.add_widget(label)

    # Buttons for delete and skip actions
    button_layout = BoxLayout(size_hint_y=None, height=50)
    delete_button = Button(text="Delete", background_color=(1, 0, 0, 1))
    delete_button.bind(on_press=lambda x: delete_action(path))
    skip_button = Button(text="Skip", background_color=(0, 1, 0, 1))
    skip_button.bind(on_press=skip_action)

    button_layout.add_widget(delete_button)
    button_layout.add_widget(skip_button)
    layout.add_widget(button_layout)

    # Show the popup
    popup = Popup(title="Confirm Deletion", content=layout, size_hint=(0.7, 0.5))
    popup.open()

def delete_action(path):
    try:
        os.remove(path)
        print(f"Deleted {path}")
    except Exception as e:
        print(f"Failed to delete {path}: {e}")
    finally:
        set_popup_inactive()
        scan_event.set()  # Signal that the popup interaction is complete

def skip_action():
    set_popup_inactive()
    scan_event.set()  # Signal that the popup interaction is complete

def set_popup_inactive():
    global popup_active
    popup_active = False

# GUI Updates and Callbacks
def update_progress(message):
    progress_text.text += message + "\n"

def show_result(message):
    progress_text.text += message + "\n"

# Function to abort the scan process
def abort_scan_process(instance):
    global abort_scan
    abort_scan = True
    progress_text.text += "Aborting scan...\n"


# Define the start_processing function
def start_processing(instance):
    progress_text.text = "Starting scan...\n"
    # Run the file scanning process in a separate thread to keep the GUI responsive
    threading.Thread(target=process_files, args=(update_progress, show_result)).start()

# Kivy Layout and UI elements
class DuplicateFileFinderApp(App):
    def build(self):
        global window, progress_text

        # Main layout
        main_layout = BoxLayout(orientation='vertical', padding=10)

        # Title label
        title_label = Label(text="Duplicate File Finder", font_size=24)
        main_layout.add_widget(title_label)

        # Progress display
        progress_text = TextInput(readonly=True, height=200, size_hint_y=None)
        main_layout.add_widget(progress_text)

        # Start and abort buttons
        button_layout = BoxLayout(size_hint_y=None, height=50)
        start_button = Button(text="Start Scan", on_press=start_processing)
        abort_button = Button(text="Abort Scan", on_press=abort_scan_process)
        button_layout.add_widget(start_button)
        button_layout.add_widget(abort_button)

        main_layout.add_widget(button_layout)

        return main_layout

# Run the app
if __name__ == "__main__":
    DuplicateFileFinderApp().run()

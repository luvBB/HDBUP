import os
import random
import subprocess
import signal
import requests
import re
from bs4 import BeautifulSoup
from config import *

# ===============================
# Functions
# ===============================

# Function to delete specific files from the current directory.
def delete_files():
    extensions_to_delete = ['.txt', '.torrent', '.png']
    directory = os.getcwd()

    def delete_file(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")

    for filename in os.listdir(directory):
        if any(filename.endswith(ext) for ext in extensions_to_delete):
            file_path = os.path.join(directory, filename)
            delete_file(file_path)
delete_files()

# Kill FFmpeg process
def kill_ffmpeg_processes():
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ffmpeg.exe'], stdout=subprocess.PIPE, text=True)
    lines = result.stdout.split('\n')
    for line in lines:
        if 'ffmpeg.exe' in line:
            pid = int(line.split()[1])
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"FFmpeg process PID {pid} has been killed.")
            except OSError:
                print(f"Error killing FFmpeg PID {pid}.")
kill_ffmpeg_processes()

# Function to get total size of a file or directory
def get_total_size(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

# Function to select piece size based on total size
def select_piece_size(total_size):
    size_gib = total_size / (1024 ** 3)  # Convert to GiB
    if size_gib < 4:
        return "2 MiB"
    elif size_gib < 8:
        return "4 MiB"
    elif size_gib < 16:
        return "8 MiB"
    else:
        return "16 MiB"

# Function to create a .torrent file
def create_torrent(input_path):
    total_size = get_total_size(input_path)
    piece_size = select_piece_size(total_size)

    if os.path.isfile(input_path) or os.path.isdir(input_path):
        output_file = os.path.join(os.getcwd(),
                                   os.path.basename(input_path.rstrip('/\\')).replace('.mkv', '') + ".torrent")
        command = [
            'torrenttools', 'create', input_path,
            '--piece-size', piece_size,
            '--output', output_file
        ]

        subprocess.run(command)
        return output_file

# ===============================
# Main Script
# ===============================

# Input direct path to file (.mkv) or folder to be uploaded
input_path = input("Input folder or mkv file path to upload: ")
if os.path.isfile(input_path) and input_path.endswith('.mkv'):
    mkv_files = [os.path.basename(input_path)]
    file_location = os.path.dirname(input_path)
elif os.path.isdir(input_path):
    file_location = input_path
    files = os.listdir(file_location)
    mkv_files = [file for file in files if file.endswith('.mkv')]
else:
    print("Invalid path.")
    exit()

if not mkv_files:
    print("No mkv files in this path.")
    exit()

selected_file = random.choice(mkv_files)
mediainfo_command = [mediainfo_path, os.path.join(file_location, selected_file)]
mediainfo_output = subprocess.check_output(mediainfo_command, encoding='utf-8').strip()
mediainfo_output = re.sub(r'Complete name\s*:\s*(.*\\)([^\\]+\.mkv)', r'Complete name                            : \2', mediainfo_output)
with open("mediainfo.txt", "w", encoding="utf-8") as output_file:
    output_file.write(mediainfo_output)

#print("File mediainfo.txt created")

# Determine video duration
duration_in_seconds = 0
for line in mediainfo_output.split('\n'):
    if "Duration" in line:
        duration_str = line.split(":")[1].strip()
        if 'h' in duration_str and 'min' in duration_str:
            hours = int(duration_str.split('h')[0].strip())
            minutes = int(duration_str.split('h')[1].split('min')[0].strip())
            duration_in_seconds = (hours * 3600) + (minutes * 60)
        elif 'min' in duration_str and 's' in duration_str:
            minutes = int(duration_str.split('min')[0].strip())
            seconds = int(duration_str.split('min')[1].split('s')[0].strip())
            duration_in_seconds = (minutes * 60) + seconds
        elif 'min' in duration_str:
            minutes = int(duration_str.split('min')[0].strip())
            duration_in_seconds = minutes * 60
        elif 's' in duration_str:
            seconds = int(duration_str.split('s')[0].strip())
            duration_in_seconds = seconds

if duration_in_seconds == 0:
    print("I couldn't determine the duration of the video.")
    exit()

# Calculate the range to avoid the first and last 10%
skip_time = int(duration_in_seconds * 0.1)  # 10% of the duration
valid_duration_in_seconds = duration_in_seconds - 2 * skip_time  # Exclude the first and last 10%

if valid_duration_in_seconds <= 0:
    raise ValueError("Video too short.")

# Take screenshots, avoiding the first and last 10%
screenshot_times = sorted(random.sample(range(0, valid_duration_in_seconds), 3))
screenshot_times = [time + skip_time for time in screenshot_times]  # Adjust times to skip the first 10%

ffmpeg_path = r"ffmpeg"
screenshot_dir = os.getcwd()
screenshot_filenames = []

for idx, time in enumerate(screenshot_times):
    screenshot_filename = os.path.join(screenshot_dir, f"screenshot_{idx+1}.png")
    ffmpeg_command = [
        ffmpeg_path,
        '-ss', str(time),
        '-i', os.path.join(file_location, selected_file),
        '-frames:v', '1',
        '-q:v', '2',
        '-an',
        '-sn',
        screenshot_filename
    ]
    process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate(input=b'\n\n')
    screenshot_filenames.append(screenshot_filename)

#print("Screenshots saved")

# ===============================
# Upload Screenshots to img.hdbits.org and maintain authentication with HDBits.org
# ===============================

# URLs
upload_url_img = 'https://img.hdbits.org/upload_form.php'
upload_url_hdbits = 'https://hdbits.org/login'  # Exemplar pentru o pagină protejată de pe hdbits.org

# Create session
session = requests.Session()

# Add cookies for both domains
for name, value in cookie_values.items():
    session.cookies.set(name, value, domain='hdbits.org')
    session.cookies.set(name, value, domain='img.hdbits.org')

# Check auth to HDBits.org
response = session.get(upload_url_hdbits)
if response.status_code == 200:
    print("Auth to HDBits OK!")
else:
    print(f"Error connecting to HDBits.org: {response.status_code}")

# Check auth to img.hdbits.org
response_img = session.get(upload_url_img)
if response_img.status_code == 200:
    print("Auth to img.hdbits OK!")
else:
    print(f"Error connecting to HDBits.org: {response_img.status_code}")

# Image URLs
uploaded_image_urls = []

# Extrage numele fișierului sau al folderului din calea de input
if os.path.isdir(input_path):
    gallery_name = os.path.basename(os.path.normpath(input_path))  # Numele folderului
elif os.path.isfile(input_path):
    gallery_name = os.path.basename(input_path).replace('.mkv', '')  # Numele fișierului fără extensia .mkv
else:
    print("Invalid input path.")
    exit()

print(f"Gallery name will be: {gallery_name}")

# Prepare all image files for upload in one request
files = {}
open_files = []  # List to keep track of open file objects
try:
    for i, screenshot_filename in enumerate(screenshot_filenames):
        img_file = open(screenshot_filename, 'rb')
        open_files.append(img_file)  # Keep track of open files
        # Add all images to the 'files' dictionary with unique keys
        files[f'images_files[{i}]'] = img_file

    # Prepare the data for gallery creation and image upload
    data = {
        'thumbsize': 'w300',            # Thumbnail size
        'galleryoption': '1',           # Create gallery
        'galleryname': gallery_name     # Numele galeriei bazat pe calea inputului
    }

    # Make a single POST request to upload all images at once
    response = session.post(upload_url_img, files=files, data=data)

    # Checking success
    if response.status_code == 200:
        print(f"Successfully created gallery '{gallery_name}' and uploaded all images")
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract the BBCode from the correct textarea
        bbcode_textarea = soup.find('textarea', onclick="this.select();")
        if bbcode_textarea:
            bbcode = bbcode_textarea.text.strip()  # Get BBCode from the textarea
            uploaded_image_urls.append(bbcode)
        else:
            print("Error: BBCode textarea not found")
    else:
        print(f"Failed to upload images. Status code: {response.status_code}")
finally:
    # Close all open files to avoid any file descriptor issues
    for img_file in open_files:
        img_file.close()

# Save BBCode links directly from the textarea to images.txt
if uploaded_image_urls:
    with open("images.txt", "w") as file:
        # Join all BBCode links into one string, separated by spaces or new lines if necessary
        bbcode = ' '.join(uploaded_image_urls)
        file.write(bbcode)

print("BBCode links saved in images.txt")

# ===============================
# Read images.txt and mediainfo.txt
# ===============================
try:
    with open("images.txt", "r", encoding="utf-8") as images_file:
        description = images_file.read()

    with open("mediainfo.txt", "r", encoding="utf-8") as mediainfo_file:
        techinfo = mediainfo_file.read()
except FileNotFoundError as e:
    print(f"Eroare: {e}")
    exit()

# ===============================
# Create Torrent and Upload
# ===============================

# Upload URL to HDBits.org
upload_url = "https://hdbits.org/upload/upload"

# Create .torrent file
torrent_file = create_torrent(os.path.join(file_location, selected_file))

if not torrent_file:
    print("Unable to create .torrent file.")
    exit()

# Preparing payload
imdb_link = input("IMDb link: ")

upload_payload = {
    'name': os.path.basename(torrent_file).replace('.torrent', ''),
    'category': '1',  # Movie
    'codec': '5',     # HEVC
    'medium': '6',    # WEB-DL
    'origin': '0',    # Undefined
    'exclusive': '0', # Non-exclusive
    'descr': description,
    'techinfo': techinfo,
    'imdb': imdb_link,
    'tvdb': '',
    'tvdb_season': '',
    'tvdb_episode': '',
    'anidb_id': ''
}


files = {
    'file': (os.path.basename(torrent_file), open(torrent_file, 'rb'))
}

upload_response = session.post(upload_url, data=upload_payload, files=files)

if upload_response.status_code == 200:
    print("Torrent uploaded to HDBits!")

    # Regular expression to find the download link, handling variable parts in the torrent filename
    regex = r'href="(/download\.php/[^"]+\.torrent\?[^"]+)"'

    # Find all matches in the text
    matches = re.findall(regex, upload_response.text)

    if matches:
        # Extracted URL and correct it by replacing &amp; with &
        torrent_url = f"https://hdbits.org{matches[0].replace('&amp;', '&')}"
        #print(f'Torrent download URL: {torrent_url}')

        # Download .torrent file
        response_torrent = session.get(torrent_url)
        if response_torrent.status_code == 200:
            # Extract torrent ID from the URL
            torrent_id_match = re.search(r'id=(\d+)', torrent_url)
            if torrent_id_match:
                torrent_id = torrent_id_match.group(1)
                torrent_filename = f'{torrent_id}.torrent'

                with open(torrent_filename, 'wb') as torrent_file:
                    torrent_file.write(response_torrent.content)
                print(f'Torrent file downloaded: {torrent_filename}')

                save_path = os.path.dirname(input_path)
                print(f'Save path set to: {save_path}')

                # Add .torrent to qBittorrent
                with open(torrent_filename, 'rb') as torrent_file:
                    files = {'torrents': torrent_file}
                    data = {
                        'savepath': save_path,
                        'autoTMM': 'false',
                        'paused': 'false',
                        'root_folder': 'true' if os.path.isdir(input_path) else 'false',
                        'dlLimit': '0',
                        'upLimit': '0',
                        'sequentialDownload': 'false',
                        'firstLastPiecePrio': 'false'
                    }

                    # Auth to qBittorrent
                    login_data = {'username': qbittorrent_username, 'password': qbittorrent_password}
                    session.post(f'{qbittorrent_url}/api/v2/auth/login', data=login_data)

                    # Add .torrent file to qBittorrent
                    qbittorrent_response = session.post(f'{qbittorrent_url}/api/v2/torrents/add', files=files, data=data)
                    if qbittorrent_response.status_code == 200 or 'Ok' in qbittorrent_response.text:
                        print(f'Torrent added to qBittorrent')
                    else:
                        print(f'Failed to add torrent to qBittorrent: {qbittorrent_response.text}')
        else:
            print(f'Failed to download torrent file: {response_torrent.status_code}')
    else:
        print("unable to found download URL.")
else:
    print(f"Error uploading: {upload_response.status_code}")

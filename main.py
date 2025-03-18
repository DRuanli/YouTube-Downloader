import sys
import argparse
import threading
import tkinter as tk
import logging
from tkinter import ttk, filedialog, messagebox
from app import YouTubeDownloader

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def console_progress_callback(percentage):
    """Progress callback for console mode"""
    print(f"Download progress: {percentage:.2f}%", end="\r")


def download_cli(url, resolution, output_path, retries=3, verbose=False):
    """Handle CLI download"""
    # Set logging level based on verbosity
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Verbose mode enabled")

    print(f"Downloading video: {url}")
    print(f"Resolution: {resolution}")
    print(f"Output directory: {output_path}")
    print(f"Maximum retries: {retries}")

    downloader = YouTubeDownloader(output_path=output_path, progress_callback=console_progress_callback)

    print("Starting download...")
    result, message = downloader.download_video(url, resolution, max_retries=retries)

    if result:
        print("\n" + message)
        print(f"Video saved to: {result}")
        return 0
    else:
        print(f"\nError: {message}")
        print("\nTroubleshooting tips:")
        print("1. Check your internet connection")
        print("2. Update pytube with: pip install --upgrade pytube")
        print("3. Verify the YouTube URL is correct and the video is available")
        print("4. Try a different resolution")
        return 1


class YouTubeDownloaderGUI:
    """GUI for YouTube Downloader"""

    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Video Downloader")
        self.root.geometry("600x400")
        self.root.resizable(True, True)

        # URL input
        url_frame = ttk.Frame(root)
        url_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(url_frame, text="YouTube URL:").pack(side="left")
        self.url_entry = ttk.Entry(url_frame, width=50)
        self.url_entry.pack(side="left", padx=5, fill="x", expand=True)

        # Resolution selection
        res_frame = ttk.Frame(root)
        res_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(res_frame, text="Resolution:").pack(side="left")
        self.resolution_var = tk.StringVar(value="highest")
        resolutions = ["highest", "lowest", "1080p", "720p", "480p", "360p"]
        resolution_menu = ttk.Combobox(res_frame, textvariable=self.resolution_var, values=resolutions,
                                       state="readonly")
        resolution_menu.pack(side="left", padx=5)

        # Output directory selection
        output_frame = ttk.Frame(root)
        output_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(output_frame, text="Save to:").pack(side="left")
        self.output_path_var = tk.StringVar(value="downloads")
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_path_var, width=40)
        self.output_entry.pack(side="left", padx=5, fill="x", expand=True)

        browse_button = ttk.Button(output_frame, text="Browse", command=self.browse_output_path)
        browse_button.pack(side="left", padx=5)

        # Download button
        button_frame = ttk.Frame(root)
        button_frame.pack(fill="x", padx=10, pady=10)

        self.download_button = ttk.Button(button_frame, text="Download", command=self.start_download)
        self.download_button.pack(side="left", padx=5)

        # Progress bar
        progress_frame = ttk.Frame(root)
        progress_frame.pack(fill="x", padx=10, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x")

        # Status label
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(root, textvariable=self.status_var)
        status_label.pack(padx=10, pady=5, anchor="w")

    def browse_output_path(self):
        """Open directory browser dialog"""
        directory = filedialog.askdirectory(initialdir=self.output_path_var.get())
        if directory:
            self.output_path_var.set(directory)

    def gui_progress_callback(self, percentage):
        """Update progress bar from download thread"""
        self.progress_var.set(percentage)
        self.status_var.set(f"Downloading: {percentage:.2f}%")
        self.root.update_idletasks()

    def start_download(self):
        """Start download in a separate thread"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL")
            return

        # Disable download button during download
        self.download_button.config(state="disabled")
        self.status_var.set("Initializing download...")
        self.progress_var.set(0)

        # Start download in a separate thread
        threading.Thread(target=self.download_thread, daemon=True).start()

    def download_thread(self):
        """Handle download in a separate thread"""
        try:
            url = self.url_entry.get().strip()
            resolution = self.resolution_var.get()
            output_path = self.output_path_var.get()

            self.status_var.set("Connecting to YouTube...")

            downloader = YouTubeDownloader(
                output_path=output_path,
                progress_callback=self.gui_progress_callback
            )

            # Show a more detailed status message
            self.status_var.set("Fetching video information...")

            # Use 3 retries by default for GUI mode
            result, message = downloader.download_video(url, resolution, max_retries=3)

            # Update GUI from main thread
            self.root.after(0, self.download_completed, result, message)

        except Exception as e:
            logger.error(f"Unhandled exception in download thread: {str(e)}")
            self.root.after(0, self.download_completed, None, f"Error: {str(e)}")

    def download_completed(self, result, message):
        """Handle download completion (called from main thread)"""
        self.download_button.config(state="normal")

        if result:
            self.status_var.set("Download complete!")
            messagebox.showinfo("Success", message)
        else:
            self.status_var.set("Download failed!")
            messagebox.showerror("Error", message)


def main_cli():
    """Command-line interface entry point"""
    parser = argparse.ArgumentParser(description="Download YouTube videos")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--resolution", "-r", default="highest",
                        help="Video resolution (highest, lowest, or specific like 720p)")
    parser.add_argument("--output", "-o", default="downloads",
                        help="Output directory for downloaded videos")
    parser.add_argument("--retries", "-t", type=int, default=3,
                        help="Maximum number of retry attempts")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose output for debugging")

    # Parse arguments
    args = parser.parse_args()

    # Proceed with CLI download
    return download_cli(args.url, args.resolution, args.output, args.retries, args.verbose)


def main():
    """Main entry point - decides between CLI and GUI"""
    if len(sys.argv) > 1:
        # If arguments provided, use CLI mode
        sys.exit(main_cli())
    else:
        # Otherwise, launch GUI
        root = tk.Tk()
        app = YouTubeDownloaderGUI(root)
        root.mainloop()


if __name__ == "__main__":
    main()
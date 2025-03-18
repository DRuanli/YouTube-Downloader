import os
from pytube import YouTube


class YouTubeDownloader:
    def __init__(self, output_path="downloads", progress_callback=None):
        """
        Initialize the YouTube downloader with an output directory.

        Args:
            output_path (str): Directory where videos will be saved
            progress_callback (function): Optional callback for progress updates
        """
        self.output_path = output_path
        self.progress_callback = progress_callback

        # Create the output directory if it doesn't exist
        if not os.path.exists(output_path):
            os.makedirs(output_path)

    def download_video(self, url, resolution="highest"):
        """
        Download a YouTube video from the given URL.

        Args:
            url (str): YouTube video URL
            resolution (str): Desired resolution, "highest" or "lowest" or specific like "720p"

        Returns:
            tuple: (file_path, message) - file_path is None if download failed
        """
        try:
            # Create a YouTube object
            yt = YouTube(url)

            # Register progress callback if provided
            if self.progress_callback:
                yt.register_on_progress_callback(self._on_progress)

            # Get video information
            title = yt.title

            # Get the appropriate stream
            if resolution == "highest":
                video = yt.streams.get_highest_resolution()
            elif resolution == "lowest":
                video = yt.streams.get_lowest_resolution()
            else:
                video = yt.streams.filter(res=resolution).first()

            if not video:
                return None, f"No video stream found with resolution {resolution}"

            # Download the video
            file_path = video.download(self.output_path)
            return file_path, f"Download complete: {title}"

        except Exception as e:
            return None, f"Error downloading video: {str(e)}"

    def _on_progress(self, stream, chunk, bytes_remaining):
        """
        Internal callback to convert pytube progress to our callback format.
        """
        if self.progress_callback:
            total_size = stream.filesize
            bytes_downloaded = total_size - bytes_remaining
            percentage = (bytes_downloaded / total_size) * 100
            self.progress_callback(percentage)
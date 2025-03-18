import os
import time
import re
import logging
from pytube import YouTube
from pytube.exceptions import RegexMatchError, HTMLParseError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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

    def download_video(self, url, resolution="highest", max_retries=3):
        """
        Download a YouTube video from the given URL.

        Args:
            url (str): YouTube video URL
            resolution (str): Desired resolution, "highest" or "lowest" or specific like "720p"
            max_retries (int): Maximum number of retry attempts

        Returns:
            tuple: (file_path, message) - file_path is None if download failed
        """
        retry_count = 0
        backoff_time = 1

        while retry_count <= max_retries:
            try:
                # Log attempt info
                if retry_count > 0:
                    logger.info(f"Retry attempt {retry_count}/{max_retries}")

                # Create a YouTube object
                yt = YouTube(url)

                # Register progress callback if provided
                if self.progress_callback:
                    yt.register_on_progress_callback(self._on_progress)

                # Get video information
                title = yt.title
                logger.info(f"Processing video: {title}")

                # Get the appropriate stream
                if resolution == "highest":
                    video = yt.streams.get_highest_resolution()
                    logger.info(f"Selected highest resolution stream")
                elif resolution == "lowest":
                    video = yt.streams.get_lowest_resolution()
                    logger.info(f"Selected lowest resolution stream")
                else:
                    video = yt.streams.filter(res=resolution).first()
                    logger.info(f"Selected {resolution} stream")

                if not video:
                    # If specific resolution not found, fall back to highest resolution
                    if resolution != "highest" and resolution != "lowest":
                        logger.warning(
                            f"No stream found with resolution {resolution}, falling back to highest available")
                        video = yt.streams.get_highest_resolution()
                        if not video:
                            return None, f"No video streams available for this video"
                    else:
                        return None, f"No video stream found with resolution {resolution}"

                # Download the video
                logger.info(f"Downloading to {self.output_path}")
                file_path = video.download(self.output_path)
                return file_path, f"Download complete: {title}"

            except RegexMatchError as e:
                logger.error(f"RegexMatchError: {str(e)}")
                # This is likely due to YouTube changes
                # We could try to fix regex patterns here
                self._fix_regex_patterns()
                retry_count += 1
                if retry_count > max_retries:
                    return None, f"Failed to parse YouTube page. YouTube may have changed their page structure."

            except HTMLParseError as e:
                logger.error(f"HTMLParseError: {str(e)}")
                retry_count += 1
                if retry_count > max_retries:
                    return None, f"Failed to parse YouTube HTML: {str(e)}"

            except Exception as e:
                logger.error(f"Error: {str(e)}")

                # Check if it's an HTTP error
                if "HTTP Error 400" in str(e) or "Bad Request" in str(e):
                    retry_count += 1
                    if retry_count > max_retries:
                        return None, "YouTube API rejected the request. Try updating pytube with: pip install --upgrade pytube"

                    # Wait before retrying with exponential backoff
                    logger.info(f"Waiting {backoff_time} seconds before retrying...")
                    time.sleep(backoff_time)
                    backoff_time *= 2  # Exponential backoff
                else:
                    # For other errors, just return immediately
                    return None, f"Error downloading video: {str(e)}"

    def _fix_regex_patterns(self):
        """
        Attempt to fix common regex pattern issues in pytube.
        This is a workaround for when YouTube changes their site structure.
        """
        try:
            # Import the necessary module to modify
            from pytube import cipher

            # Update the regex pattern for js function name extraction
            # (This pattern might need adjusting based on current YouTube structure)
            cipher.get_initial_function_name_regex = re.compile(
                r'(?P<function_name>[a-zA-Z$_]\w*)\s*=\s*function\(\w+\)')
            cipher.get_transform_plan_regex = re.compile(r'(?P<transform_plan>\w+\..+?)\(')

            logger.info("Updated pytube regex patterns")
        except Exception as e:
            logger.error(f"Failed to update regex patterns: {str(e)}")
            # Continue anyway and hope for the best

    def _on_progress(self, stream, chunk, bytes_remaining):
        """
        Internal callback to convert pytube progress to our callback format.
        """
        if self.progress_callback:
            total_size = stream.filesize
            bytes_downloaded = total_size - bytes_remaining
            percentage = (bytes_downloaded / total_size) * 100
            self.progress_callback(percentage)
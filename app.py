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

                # Create a YouTube object with custom callback to work around title issues
                yt = YouTube(
                    url,
                    on_progress_callback=self._on_progress if self.progress_callback else None,
                    use_oauth=False,
                    allow_oauth_cache=False
                )

                # Try to get title safely - this is a common failure point
                try:
                    title = yt.title
                    logger.info(f"Processing video: {title}")
                except Exception as title_error:
                    logger.warning(f"Could not access video title: {str(title_error)}")
                    # Use video ID as fallback title
                    video_id = url.split("v=")[1].split("&")[0] if "v=" in url else "unknown"
                    title = f"youtube_{video_id}"
                    logger.info(f"Using fallback title: {title}")

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

                # Check for known pytube errors that we might be able to work around
                error_str = str(e)
                if any(x in error_str for x in ["HTTP Error 400", "Bad Request", "title", "Exception while accessing"]):
                    # These are all potentially fixable with pattern updates and retries
                    self._fix_regex_patterns()

                    retry_count += 1
                    if retry_count > max_retries:
                        return None, "YouTube API rejected the request. Please try:\n1. pip install --upgrade pytube\n2. pip install git+https://github.com/pytube/pytube.git"

                    # Wait before retrying with exponential backoff
                    logger.info(f"Waiting {backoff_time} seconds before retrying...")
                    time.sleep(backoff_time)
                    backoff_time *= 2  # Exponential backoff
                else:
                    # Try to detect if this is a region restriction or age verification issue
                    if "age" in error_str.lower() or "restrict" in error_str.lower() or "unavailable" in error_str.lower():
                        return None, f"This video may be restricted or age-limited: {error_str}"
                    else:
                        # For other errors, retry once then give up
                        retry_count += 1
                        if retry_count > 1:  # Only retry once for unknown errors
                            return None, f"Error downloading video: {error_str}"
                        logger.info("Retrying once for unknown error...")
                        time.sleep(1)

    def _fix_regex_patterns(self):
        """
        Attempt to fix common regex pattern issues in pytube.
        This is a comprehensive fix for when YouTube changes their site structure.
        """
        try:
            # Import necessary modules to modify
            from pytube import cipher
            from pytube.innertube import InnerTube

            # Update several common regex patterns that often break
            cipher.get_initial_function_name_regex = re.compile(r'(?P<var>[a-zA-Z$_][a-zA-Z0-9$_]*)=function\(\w+\)')
            cipher.get_transform_plan_regex = re.compile(r'(?P<transform_plan>[a-zA-Z$_][a-zA-Z0-9$_]*\..+?)\(')
            cipher.get_transform_object_regex = re.compile(r'var (?P<transform_object>[a-zA-Z$_][a-zA-Z0-9$_]*)=\{')
            cipher.get_transform_object_dict_regex = re.compile(r'(?P<object_dict>({.+?}))')

            # Reset the client cache - sometimes helps with stale client issues
            InnerTube._default_clients = {}

            # Patch client/get calls for JS object retrieval
            try:
                from pytube.extract import get_ytplayer_config, find_object_from_startpoint
                from pytube.parser import find_object_from_startpoint as parser_find

                # Ensure these functions have the strongest regex patterns
                get_ytplayer_config.__defaults__ = (r'window\.ytplayer\.config\s*=\s*', r'ytplayer\.config\s*=\s*',)

                logger.info("Patched internal pytube functions")
            except (ImportError, AttributeError) as e:
                logger.warning(f"Could not patch all internal functions: {str(e)}")

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
from typing import Union, Tuple, Dict, Any
import io
from PIL import Image
import os

class ImageLoader:
    def __init__(self):
        self.supported_extensions = ('.png', '.jpg', '.jpeg')

    def load_image(self, path: str) -> Tuple[Image.Image, Dict[str, Any]]:
        """
        Load an image from disk and return it along with metadata.

        Parameters:
        - path (str): The path to the image file.

        Returns:
        - Tuple[Image.Image, Dict[str, Any]]: A tuple containing the image object and metadata.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Image not found at {path}")

        extension = os.path.splitext(path)[1].lower()
        if extension not in self.supported_extensions:
            raise ValueError(f"Unsupported file format. Only {', '.join(self.supported_extensions)} are supported.")

        with io.BytesIO() as buffer:
            with open(path, 'rb') as file:
                buffer.write(file.read())
                buffer.seek(0)
            image = Image.open(buffer)

        metadata: Dict[str, Any] = {}
        metadata['file_path'] = path
        metadata['file_size'] = os.path.getsize(path)
        metadata['width'], metadata['height'] = image.size
        metadata['format'] = image.format
        metadata['mode'] = image.mode

        return image, metadata

# Usage example:
# loader = ImageLoader()
# image, info = loader.load_image('path/to/image.jpg')
# print(info)
from PIL import Image
import numpy as np

class ImageResize:
    def __init__(self, image_path):
        self.image = Image.open(image_path)
        self.width, self.height = self.image.size

    def resize(self, new_width, new_height):
        """
        Resize the image to a new width and height while preserving image quality.

        Args:
            new_width (int): The new width of the image.
            new_height (int): The new height of the image.

        Returns:
            Image: The resized image.
        """
        # Calculate the aspect ratio
        aspect_ratio = self.width / self.height

        # Determine if resizing is necessary
        if new_width <= self.width and new_height <= self.height:
            return self.image

        # Calculate new dimensions
        if new_width < self.width or new_height < self.height:
            # Resize to the minimum dimension while maintaining aspect ratio
            if self.width > self.height:
                new_height = round(new_width / aspect_ratio)
            else:
                new_width = round(new_height * aspect_ratio)
        else:
            # Resize to the maximum dimension while maintaining aspect ratio
            if self.width < self.height:
                new_width = round(new_height * aspect_ratio)
            else:
                new_height = round(new_width / aspect_ratio)

        # Resize the image
        resized_image = self.image.resize((new_width, new_height), Image.ANTIALIAS)
        return resized_image

    def save(self, output_path):
        """
        Save the resized image to a file.

        Args:
            output_path (str): The path to save the image.
        """
        self.resized_image.save(output_path)

    def get_size(self):
        """
        Get the new size of the image.

        Returns:
            tuple: The new width and height of the image.
        """
        return self.resized_image.size
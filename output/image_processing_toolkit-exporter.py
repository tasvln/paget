import numpy as np
from PIL import Image

def save_image(image, path):
    """
    Save a processed image to a specified path.

    Args:
        image (numpy.ndarray): Image to save, in RGB format (0-255).
        path (str): Filepath to save the image to.
    """
    if image.ndim != 3:
        raise ValueError("Input image must be 3D (height, width, channels).")
    
    if image.shape[2] != 3:
        raise ValueError("Image must be in RGB format (3 channels).")
    
    if np.max(image) > 255.0 or np.min(image) < 0.0:
        raise ValueError("Image pixel values must be in the range [0, 255].")
    
    # Convert to uint8
    if image.dtype != np.uint8:
        image = image.astype(np.uint8)
    
    # Save as PNG
    Image.fromarray(image).save(path)

# Example usage:
# save_image(np.random.randint(0, 256, (100, 200, 3)), 'output.png')
import numpy as np
from PIL import Image

def create_average_color(image_path):
    """
    Calculate the average color of an image.

    Parameters:
    - image_path: str, path to the image file

    Returns:
    - tuple, (R, G, B) average color
    """
    # Open image
    img = Image.open(image_path)
    
    # Convert to RGB (if it's not already)
    img = img.convert('RGB')
    
    # Convert to numpy array
    img_array = np.array(img)
    
    # Calculate average color
    avg_color = (img_array.mean(axis=(0, 1)))
    
    return tuple(avg_color)

def create_histogram(image_path):
    """
    Create a histogram of pixel intensities for an image.

    Parameters:
    - image_path: str, path to the image file

    Returns:
    - dict, histogram counts for each channel
    """
    # Open image
    img = Image.open(image_path)
    
    # Convert to RGB (if it's not already)
    img = img.convert('RGB')
    
    # Convert to numpy array
    img_array = np.array(img)
    
    # Histogram calculation
    hist = {c: np.histogram(img_array[:, :, c], bins=256)[0] for c in range(3)}
    
    return hist
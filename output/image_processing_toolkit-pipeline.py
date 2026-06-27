from typing import List, Callable, Optional, Union

class ImagePipeline:
    def __init__(self):
        self.operations: List[Callable] = []

    def add(self, op: Callable):
        self.operations.append(op)
        return self

    def process(self, image):
        for op in self.operations:
            image = op(image)
        return image

    def __rshift__(self, other):
        """Allows for chaining operations with >>"""
        if not callable(other):
            raise TypeError(f"Unsupported operand type for >>: '{other.__class__.__name__}'")
        return ImagePipeline().add(other)

    def __call__(self, image):
        """Allows for calling the pipeline directly"""
        return self.process(image)

# Example usage
def crop(image):
    # Simulate cropping
    return f"Cropped {image}"

def resize(image):
    # Simulate resizing
    return f"Resized {image}"

def apply_filter(image):
    # Simulate applying a filter
    return f"Filtered {image}"

# Creating a pipeline
pipeline = ImagePipeline()
pipeline = pipeline.add(crop) >> resize >> apply_filter

# Processing an image
image = "Original Image"
processed_image = pipeline(image)
print(processed_image)
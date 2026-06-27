class ImageFilter:
    def __init__(self):
        pass

    def create_grayscale(self, image):
        """
        Convert an image to grayscale.

        :param image: Input image (usually a 2D list of pixel values)
        :return: Grayscale image
        """
        if not image:
            return []

        grayscale_image = []
        for row in image:
            new_row = []
            for pixel in row:
                # Convert RGB to grayscale (equation: 0.299R + 0.587G + 0.114B)
                # This is the luminance formula
                gray = int(0.299 * pixel[0] + 0.587 * pixel[1] + 0.114 * pixel[2])
                new_row.append((gray, gray, gray))
            grayscale_image.append(new_row)
        return grayscale_image

    def create_invert(self, image):
        """
        Invert the colors of an image.

        :param image: Input image (usually a 2D list of pixel values)
        :return: Inverted image
        """
        if not image:
            return []

        inverted_image = []
        for row in image:
            new_row = []
            for pixel in row:
                # Invert each channel (255 - R, 255 - G, 255 - B)
                inverted_row = []
                for channel in pixel:
                    inverted_channel = 255 - channel
                    inverted_row.append(inverted_channel)
                new_row.append(inverted_row)
            inverted_image.append(new_row)
        return inverted_image

    def create_brightness(self, image, value):
        """
        Adjust the brightness of an image.

        :param image: Input image (usually a 2D list of pixel values)
        :param value: Brightness adjustment value (e.g., 255 to increase)
        :return: Brightness-adjusted image
        """
        if not image:
            return []

        brightness_image = []
        for row in image:
            new_row = []
            for pixel in row:
                # Calculate new brightness for each channel
                new_channel = min(255, max(0, pixel + value))
                new_row.append((new_channel, new_channel, new_channel))
            brightness_image.append(new_row)
        return brightness_image
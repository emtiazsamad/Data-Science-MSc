from PIL import Image
import numpy as np

def preprocess(frame):
    image = Image.fromarray(frame)
    image = image.convert("L")
    image = image.crop((0, 34, 160, 194))
    image = np.array(image.resize((84, 84))) / 255.0
    return image.astype(np.float32)
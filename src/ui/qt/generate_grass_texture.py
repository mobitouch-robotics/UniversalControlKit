# Placeholder for a simple grass texture (green noise)
from PIL import Image
import numpy as np

def generate_grass_texture(path="grass_texture.png", size=256):
    np.random.seed(42)
    base = np.random.normal(loc=180, scale=30, size=(size, size, 3)).astype(np.uint8)
    base[..., 0] = np.clip(base[..., 0] * 0.7, 0, 255)  # Reduce red
    base[..., 2] = np.clip(base[..., 2] * 0.5, 0, 255)  # Reduce blue
    img = Image.fromarray(base, mode="RGB")
    img.save(path)

if __name__ == "__main__":
    generate_grass_texture()

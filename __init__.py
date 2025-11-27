"""
ComfyUI Model Downloader Custom Node
HuggingFace and CivitAI model downloader for ComfyUI
With models.ini management for reproducibility
"""

from .model_downloader import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

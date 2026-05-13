"""
Document Processing Module - Parse and extract compliance frameworks from documents.
"""
from .parser import document_parser, DocumentParser
from .framework_extractor import framework_extractor, FrameworkExtractor

__all__ = [
    'document_parser',
    'DocumentParser',
    'framework_extractor',
    'FrameworkExtractor'
]

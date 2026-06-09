class EmbeddingError(Exception):
    """Raised when text embedding fails."""
    pass


class GenerationError(Exception):
    """Raised when text generation fails."""
    pass


class TrainingDataNotFoundError(Exception):
    """Raised when training data file cannot be found."""
    pass


class PineconeConnectionError(Exception):
    """Raised when connection to Pinecone fails."""
    pass

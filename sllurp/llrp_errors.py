class LLRPError(Exception):
    pass


class LLRPResponseError(LLRPError):
    pass


class ReaderConfigurationError(LLRPError):
    pass

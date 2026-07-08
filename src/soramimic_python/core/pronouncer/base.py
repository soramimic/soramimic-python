from abc import ABC, abstractmethod

class BasePronouncer(ABC):
    @abstractmethod
    def pronounce(self, text: str) -> str:
        pass
    
    @abstractmethod
    def get_match_pattern_with_tag(self, tag: str) -> str:
        pass
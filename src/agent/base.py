from abc import ABC, abstractmethod


class AgentBase(ABC):

    @abstractmethod
    def invoke(self, query: str):
        """Send a message and return the agent's response."""
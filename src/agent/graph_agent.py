"""Graph agent class."""
from typing import Any, Callable, Literal, Optional
from langchain.messages import ToolMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.types import RetryPolicy
from langchain.tools import tool
from langchain.chat_models import BaseChatModel, init_chat_model
from langgraph.graph import StateGraph, START, END
from langfuse import get_client
from langfuse.langchain import CallbackHandler

from src.agent.models import MessagesState
from langgraph.checkpoint.memory import InMemorySaver

langfuse = get_client()
 
# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

class GraphAgent:

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0, **kwargs):
        self.model: BaseChatModel = init_chat_model(model=model, temperature=temperature, **kwargs)
        self.config = {"configurable": {"thread_id": "1"}}
        self.langfuse_handler = CallbackHandler()
        self.agent = self._compile_agent()

    @tool
    @staticmethod
    def multiply(a: int, b: int) -> int:
        """Multiply `a` and `b`.

        Args:
            a: First int
            b: Second int
        """
        return a * b


    @tool
    @staticmethod
    def add(a: int, b: int) -> int:
        """Adds `a` and `b`.

        Args:
            a: First int
            b: Second int
        """
        return a + b

    @tool
    @staticmethod
    def subtract(a: int, b: int) -> int:
        """Subtracts `a` from `b`.

        Args:
            a: First int
            b: Second int
        """
        return b - a

    @tool
    @staticmethod
    def divide(a: int, b: int) -> float:
        """Divide `a` and `b`.

        Args:
            a: First int
            b: Second int
        """
        return a / b

    def llm_call(self, model_with_tools: Callable):
        """LLM decides whether to call a tool or not"""

        prompt = ChatPromptTemplate.from_messages([
            ("system",  "You are a helpful assistant. You have access to arithmetic tools (add, subtract, multiply, divide) "
                        "and should use them when the user asks for calculations. For general questions, answer directly."),
            MessagesPlaceholder(variable_name="messages"),
        ])
        chain = ( prompt | model_with_tools )
        
        def create_llm_call_node(state: dict):
            """Create an LLM call node"""
            response = chain.invoke(
                {"messages": state["messages"]},
                config={"callbacks": [self.langfuse_handler]}
            )
            return {
                "messages": [response],
                "llm_calls": state.get('llm_calls', 0) + 1
            }
    
        return create_llm_call_node

    def tool_node(self, tools_by_name: dict):
        """Performs the tool call"""

        def create_tool_node(state: dict):
            """Create a tool node"""
            result = []
            for tool_call in state["messages"][-1].tool_calls:
                tool = tools_by_name[tool_call["name"]]
                observation = tool.invoke(tool_call["args"])
                result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
            return {"messages": result}
        
        return create_tool_node

    @staticmethod
    def should_continue(state: MessagesState) -> Literal["tool_node", END]: # type: ignore
        """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

        messages = state["messages"]
        last_message = messages[-1]

        # If the LLM makes a tool call, then perform an action
        if last_message.tool_calls: # type: ignore
            return "tool_node"

        # Otherwise, we stop (reply to the user)
        return END

    def _compile_agent(self):
        """Run the graph agent."""
        # Augment the LLM with tools
        tools = [self.add, self.subtract, self.multiply, self.divide]
        tools_by_name = {tool.name: tool for tool in tools}
        model_with_tools = self.model.bind_tools(tools)

        # Build workflow
        agent_builder = StateGraph(MessagesState)

        # Add nodes
        agent_builder.add_node("llm_call", self.llm_call(model_with_tools=model_with_tools)) # type: ignore
        agent_builder.add_node("tool_node", self.tool_node(tools_by_name=tools_by_name), retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0)) # type: ignore

        # Add edges to connect nodes
        agent_builder.add_edge(START, "llm_call")
        agent_builder.add_conditional_edges(
            "llm_call",
            self.should_continue,
            ["tool_node", END]
        )
        agent_builder.add_edge("tool_node", "llm_call")

        # Compile the agent
        checkpointer = InMemorySaver()
        return agent_builder.compile(checkpointer=checkpointer)

    def invoke(
        self,
        input: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Invoke the agent with Langfuse tracing attributes."""
        message = HumanMessage(content=input)
        # Build optional tags without leaking sensitive data.
        tags = [f"tenant:{tenant_id}"] if tenant_id else []

        self.langfuse_handler.trace_name = "agent-invoke"
        self.langfuse_handler.session_id = session_id or tenant_id
        self.langfuse_handler.user_id = user_id
        self.langfuse_handler.tags = tags or None
        self.langfuse_handler.metadata = {"tenant_id": tenant_id} if tenant_id else None

        run_config: dict[str, Any] = {**self.config, "callbacks": [self.langfuse_handler]}
        initial_state: MessagesState = {"messages": [message], "llm_calls": 0}
        response = self.agent.invoke(  # type: ignore[arg-type]
            initial_state,
            config=run_config,  # type: ignore[arg-type]
        )

        # Garante que os dados sejam enviados ao Langfuse antes de retornar,
        # importante especialmente em ambientes de execução curta (scripts, testes)
        langfuse.flush()

        return response["messages"].pop().content


if __name__ == "__main__":
    agent = GraphAgent("claude-haiku-4-5")
    command = "Ayrton Senna?"
    result = agent.invoke(command)
    print(result)

    command = "SR-71 max speed?"
    result = agent.invoke(command)
    print(result)

    command = "What was my first question?"
    result = agent.invoke(command)
    print(result)
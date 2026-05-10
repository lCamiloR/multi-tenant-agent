"""Graph agent class."""
from typing import Any, Callable, Literal, Optional
from langchain.messages import ToolMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.types import RetryPolicy
from langchain_core.runnables import RunnableLambda
from langchain.chat_models import BaseChatModel, init_chat_model
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langfuse import get_client
from langfuse.langchain import CallbackHandler
from datetime import datetime
from logging import getLogger

from src.agent.base import AgentBase
from src.agent.models.execution_state import ExecutionState
from src.agent.models.enums import Phases
from src.agent.models.outputs import IsStepComplete
from langgraph.checkpoint.memory import InMemorySaver
from src.utils.formatters import build_capabilities

langfuse = get_client()
logger = getLogger(__name__)
 
# Verify connection
if not langfuse.auth_check():
    logger.error("Authentication failed. Please check your credentials and host.")

class GraphAgent(AgentBase):
    """GraphAgent class."""
    
    def __init__(self, model: str = "gpt-4o-mini", context_tools: Optional[list[Any]] = None, execution_tools: Optional[list[Any]] = None, **kwargs):
        """Initialize the GraphAgent."""
        self.model: BaseChatModel = init_chat_model(model=model, temperature=0.6, **kwargs)
        self.config: dict = {"configurable": {"thread_id": "1"}}
        self.langfuse_handler: CallbackHandler = CallbackHandler()
        self.context_capabilities: Optional[str] = build_capabilities(context_tools) if context_tools else None
        self.execution_capabilities: Optional[str] = build_capabilities(execution_tools) if execution_tools else None
        self.agent: CompiledStateGraph = self._compile_agent()

    # ---------------------------------
    #               UTIL
    # ---------------------------------
    def save_graph_schema(self, graph: CompiledStateGraph):
        """Save the graph schema."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"./plan_execute_graph_{timestamp}.mmd"

        mermaid_code = graph.get_graph(xray=True).draw_mermaid()
        with open(file_path, "w") as f:
            f.write(mermaid_code)
        logger.info(f"Graph Schema Saved!")

    # ---------------------------------
    #               NODES
    # ---------------------------------
    def make_assistant_node(
        self,
        system_prompt: str,
        dynamic_prompt: str,
        tools = None,
        input_mapper = None,
        llm_output_transformer = lambda state: {"messages": state["messages"]},
        output_mapper = lambda result, _: {"messages": [result]},
    ):
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", dynamic_prompt)
        ])
        inputs = RunnableLambda(input_mapper)

        # LLM FUNNEL
        llm = self.model
        if tools:
            llm = llm.bind_tools(tools)
        if llm_output_transformer:
            llm = llm_output_transformer(llm)
        
        chain = inputs | prompt | llm

        def assistant_node(state: ExecutionState) -> ExecutionState:
            result = chain.invoke(state)

            result_state = output_mapper(result, state)
            return  { **result_state }
        
        return assistant_node

    def make_step_revisor_node(
            self,
            system_prompt: str,
            dynamic_prompt: str,
            input_mapper = None,
            mode: str = "research"
            ):
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", dynamic_prompt)
        ])
        inputs = RunnableLambda(input_mapper)

        chain =  ( inputs | prompt | self.model.with_structured_output(IsStepComplete))

        def research_revisor_node(state: ExecutionState) -> ExecutionState:
            result = chain.invoke(state)

            # PROXIMO PASSO ou PLANO COMPLETO
            next_counter = state["step_counter"] + 1

            if next_counter >= len(state["research_plan"].steps):
                return {
                    "messages": [ ("ai", "Pesquisa de Contexto Concluída!")],
                    "step_counter": -1,
                    "phase": Phases.CONTEXT_CONSOLIDATION
                }
            elif result.isComplete:
                return {
                    "messages": [("ai", f"Passo concluído, seguindo para o próximo passo...")],
                    "step_counter": next_counter,
                    "phase": Phases.CONTEXT_GATHERING
                }


        def step_revisor_node(state: ExecutionState) -> ExecutionState:
            result = chain.invoke(state)

            # PROXIMO PASSO ou PLANO COMPLETO
            next_counter = state["step_counter"] + 1

            if next_counter >= len(state["research_plan"].steps):
                return {
                    "messages": [ ("ai", "Passos do Plano Concluídos!")],
                    "step_counter": -1,
                    "phase": Phases.WRAPPING_UP
                }
            elif result.isComplete:
                return {
                    "messages": [("ai", f"Passo concluído, seguindo para o próximo passo...")],
                    "step_counter": next_counter,
                    "phase": Phases.EXECUTING
                }

        if mode == "research":
            return research_revisor_node
        return step_revisor_node

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
    def should_continue(state: ExecutionState) -> Literal["tool_node", END]: # type: ignore
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
        agent_builder = StateGraph(ExecutionState)

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
        query: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Invoke the agent with Langfuse tracing attributes."""
        message = HumanMessage(content=query)
        # Build optional tags without leaking sensitive data.
        tags = [f"tenant:{tenant_id}"] if tenant_id else []

        self.langfuse_handler.trace_name = "agent-invoke"
        self.langfuse_handler.session_id = session_id or tenant_id
        self.langfuse_handler.user_id = user_id
        self.langfuse_handler.tags = tags or None
        self.langfuse_handler.metadata = {"tenant_id": tenant_id} if tenant_id else None

        run_config: dict[str, Any] = {**self.config, "callbacks": [self.langfuse_handler]}
        initial_state: ExecutionState = {"messages": [message], "llm_calls": 0}
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

    # command = "SR-71 max speed?"
    # result = agent.invoke(command)
    # print(result)

    # command = "What was my first question?"
    # result = agent.invoke(command)
    # print(result)
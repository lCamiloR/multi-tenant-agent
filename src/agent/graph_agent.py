"""Graph agent class."""
from typing import Any, Optional
from langchain.messages import HumanMessage, SystemMessage
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
        # llm_output_transformer = lambda state: {"messages": state["messages"]},
        output_mapper = lambda result, _: {"messages": [result]},
    ):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(system_prompt),
            ("user", dynamic_prompt),
        ])
        inputs = RunnableLambda(input_mapper)

        # LLM FUNNEL
        llm = self.model
        if tools:
            llm = llm.bind_tools(tools)
        
        # if llm_output_transformer:
        #     llm = llm_output_transformer(llm)
        
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

            # NEXT STEP or PLAN COMPLETE
            next_counter = state["step_counter"] + 1

            if next_counter >= len(state["research_plan"].steps):
                return {
                    "messages": [ ("ai", "Context Research Completed!")],
                    "step_counter": -1,
                    "phase": Phases.CONTEXT_CONSOLIDATION
                }
            elif result.isComplete:
                return {
                    "messages": [("ai", f"Step completed, moving to the next step...")],
                    "step_counter": next_counter,
                    "phase": Phases.CONTEXT_GATHERING
                }


        def step_revisor_node(state: ExecutionState) -> ExecutionState:
            result = chain.invoke(state)

            # NEXT STEP or PLAN COMPLETE
            next_counter = state["step_counter"] + 1

            if next_counter >= len(state["research_plan"].steps):
                return {
                    "messages": [ ("ai", "Plan Steps Completed!")],
                    "step_counter": -1,
                    "phase": Phases.WRAPPING_UP
                }
            elif result.isComplete:
                return {
                    "messages": [("ai", f"Step completed, moving to the next step...")],
                    "step_counter": next_counter,
                    "phase": Phases.EXECUTING
                }

        if mode == "research":
            return research_revisor_node
        return step_revisor_node

    def _compile_agent(self):
        """Run the graph agent."""
        # Augment the LLM with tools
        tools = []
        tools_by_name = {tool.name: tool for tool in tools}
        model_with_tools = self.model.bind_tools(tools)

        # Names
        TEST_NODE = "test"

        # Node config
        test_node = self.make_assistant_node(
            system_prompt = "Your are a conversational assistent, capable of answering any given query.",
            dynamic_prompt = "Messages: \n {messages} \n",
            input_mapper = lambda state: {"messages": state["messages"]},
            output_mapper=lambda result, _: {"messages": [result]},
        )

        # Build workflow
        agent_builder = StateGraph(ExecutionState)

        # Add nodes
        agent_builder.add_node(TEST_NODE, test_node, retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0)) # type: ignore

        # Add edges to connect nodes
        agent_builder.add_edge(START, TEST_NODE)
        agent_builder.add_edge(TEST_NODE, END)

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
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "phase": Phases.INITIAL,
            "step_counter": 0,
        }

        for event in self.agent.stream(
            initial_state,
            config=self.config,
        ):
            yield event
        # message = HumanMessage(content=query)
        # # Build optional tags without leaking sensitive data.
        # tags = [f"tenant:{tenant_id}"] if tenant_id else []

        # self.langfuse_handler.trace_name = "agent-invoke"
        # self.langfuse_handler.session_id = session_id or tenant_id
        # self.langfuse_handler.user_id = user_id
        # self.langfuse_handler.tags = tags or None
        # self.langfuse_handler.metadata = {"tenant_id": tenant_id} if tenant_id else None

        # run_config: dict[str, Any] = {**self.config, "callbacks": [self.langfuse_handler]}
        # initial_state: ExecutionState = {"messages": [message], "llm_calls": 0}
        # response = self.agent.invoke(  # type: ignore[arg-type]
        #     initial_state,
        #     config=run_config,  # type: ignore[arg-type]
        # )

        # # Ensures data is flushed to Langfuse before returning,
        # # important especially in short-lived execution environments (scripts, tests)
        # langfuse.flush()

        # return response["messages"].pop().content


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
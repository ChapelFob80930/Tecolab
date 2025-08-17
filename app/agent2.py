from pprint import pprint
from typing import Annotated, Sequence, List, Literal, Optional
from typing_extensions import TypedDict
from dotenv import load_dotenv
import os
import json
from uuid import uuid4
# from .config import settings  ##NOTE: Will uncomment this once API is setup, now using load_dotenv to load environment variables as using this import causes ImportError: attempted relative import with no known parent package but works when called from the main file
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    BaseMessage,
    ToolMessage,
    SystemMessage,
    HumanMessage,
    get_buffer_string,
    AIMessage
)
from langchain_core.tools import tool
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_tavily import TavilySearch
# from .course_outline_generation import generate_course_outline ##Note: Same as above, will uncomment once API is setup
from .course_outline_generation import generate_course_outline
from .schemas import CourseOutline, CoursePrompt
import tiktoken
from langchain_core.runnables import RunnableConfig
import uuid
from .course_outline_generation import parse_user_input_for_course_outline, generate_course_outline
from .course_generation import generate_module_content
from pathlib import Path
# from vector_database import get_vector_db
from .supabase import get_db, session_scope
from .supabase_models import AgentMemory
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import text
from typing import List
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from typing import Literal
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
import operator
from langchain_ollama.llms import OllamaLLM
from langchain_ollama import OllamaEmbeddings
from .supabase import SessionLocal
from .checkpoint import SupabaseCheckpointSaver


load_dotenv()

# embeddings = OpenAIEmbeddings()
embeddings = OllamaEmbeddings(
    model="llama2",
)

# recall_vector_store = InMemoryVectorStore(OpenAIEmbeddings())

# vector_store: Session = next(get_db())

# llm = ChatOpenAI(model = "gpt-4o-mini", temperature=0)
llm = OllamaLLM(model="llama2", temperature=0)

## HELPER FUNCTIONS

def intent_checker(HumanMessage: str) -> str:
    intent_check_prompt = PromptTemplate.from_template(
        """
            You are a routing assistant for an AI course creation agent.

            Decide what the user wants to do based on their message.

            User message: "{user_input}"

            If they want to modify the existing course outline (e.g., add, remove, change something), respond with:
            edit_outline

            If they want to generate a new course or continue generation, respond with:
            generate_course
        """
    )

    intent_chain = (intent_check_prompt | llm | StrOutputParser())
    
    return intent_chain.invoke({"user_input": HumanMessage})

def check_module_feedback_intent(message: str) -> str:
    """
    Use LLM to determine if user approves the module or wants to edit it.

    Returns:
    - "approve"
    - "edit"
    - "unclear"
    """
    prompt = PromptTemplate.from_template("""
    You are a helpful assistant helping a course generation agent. Based on the user's message, determine their intent.

    Message: "{message}"

    Respond ONLY with one of the following:
    - approve
    - edit
    - unclear
    """)
    
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"message": message}).strip().lower()



## ACTUAL AGENT CODE
#Reducer function to keep the first value, ignore subsequent ones
  


class AgentState(TypedDict):
    # user_id: str
    user_id: str
    # course_id: str
    course_id: dict
    messages: Annotated[Sequence[BaseMessage], add_messages]
    course_outline: str
    # course_outline: Annotated[str, operator.add]
    course: str
    current_content: Optional[str]  # for tools
    module_index: int                      # New: which module is currently being generated
    generated_modules: List[str]          # New: list of fully generated module texts
    awaiting_approval: bool               # New: whether we're waiting for user input
    # status: Optional[Literal["approved", "feedback"]]  # New: text to review, if any
    user_edit_request: Optional[str]
    # step: Literal["course_outline_generation", "course_generation", "finished"]




# @tool
# def web_scraping(content: str):
#     pass

# @tool
# def get_yt_links(content: str):
#     pass

# @tool
# def save_recall_memory(memory: AgentState, config: RunnableConfig) -> str:
def save_recall_memory(memory: AgentState) -> str:
    """
    Save memory (course content & course outline) to vectorstore (Supabase)
    for later semantic retrieval whenever course content or outline is generated or updated.
    """
    print("Saving memory to vector store...")
    
    user_id = memory["user_id"]
    course_id = memory["course_id"]

    # Ensure course_outline is a string for embedding
    course_outline_str = (
        memory["course_outline"]
        if isinstance(memory["course_outline"], str)
        else json.dumps(memory["course_outline"])
    )
    course_outline_embedding = embeddings.embed_query(course_outline_str)

    # Handle optional course content
    course_content_embedding = None
    if memory.get("generated_modules"):
        course_str = (
            memory["generated_modules"]
            if isinstance(memory["generated_modules"], str)
            else json.dumps(memory["generated_modules"])
        )
        course_content_embedding = embeddings.embed_query(course_str)

    # Insert into Supabase using SQLAlchemy session
    with session_scope() as db:
        db.execute(
            text("""
                INSERT INTO agent_memory (
                    user_id,
                    course_id,
                    course_outline,
                    course_outline_embeddings,
                    course_content,
                    course_content_embeddings,
                    final_course,
                    final_course_outline,
                    final_course_outline_embeddings
                )
                VALUES (:user_id, :course_id, :outline, :outline_vec, :content, :content_vec, :final_course, :final_outline, :final_outline_vec)
                ON CONFLICT (user_id, course_id) DO UPDATE
                SET course_outline_embeddings = EXCLUDED.course_outline_embeddings,
                    course_content_embeddings = EXCLUDED.course_content_embeddings
            """),
            {
                "user_id": user_id,
                "course_id": course_id,
                "outline": memory["course_outline"] if memory["course_outline"] else "",
                "outline_vec": course_outline_embedding,
                "content": memory["generated_modules"] if memory["generated_modules"] else "",
                "content_vec": course_content_embedding,
                "final_course":memory["generated_modules"] if memory["generated_modules"] else "",
                "final_outline": memory["course_outline"] if memory["course_outline"] else "",
                "final_outline_vec": course_outline_embedding if course_outline_embedding else None
            }
        )

    return "Memory saved successfully."

# @tool
# def search_recall_memories(query: str, config: RunnableConfig, user_id: int, course_id: str) -> List[str]:
def search_recall_memories(query: str, user_id: int, course_id: str) -> List[str]:
    """
    Search for semantically similar memory chunks when generating
    the course outline (i.e., when the agent is initially activated).
    """
    # Create embedding for the search query
    query_embedding = embeddings.embed_query(query)

    # Run search query against Supabase/Postgres
    with session_scope() as db:
        results = db.execute(
            text("""
                SELECT course_content
                FROM agent_memory
                WHERE user_id = :user_id AND course_id = :course_id
                ORDER BY course_content_embedding <-> :query_embedding
                LIMIT 3
            """),
            {
                "user_id": user_id,
                "course_id": course_id,
                "query_embedding": query_embedding
            }
        ).fetchall()

    return [row[0] for row in results]


def human_feedback(state: AgentState):
    pass


def course_outline_workflow_node(state: AgentState) -> AgentState:
    """
    Combined workflow:
    1. Generate a course outline from user input.
    2. If awaiting_approval is False → Generate and set awaiting_approval to True.
    3. If awaiting_approval is True and user_edit_request exists → Edit the outline.
    """

    user_message = next((msg for msg in reversed(state["messages"]) if isinstance(msg, HumanMessage)), None)
    if not user_message:
        raise ValueError("No user message found.")

    # If we are awaiting approval and the user gave an edit request → run edit mode
    if state.get("awaiting_approval") and state.get("user_edit_request"):
        print("Editing course outline based on user request...")

        parser = PydanticOutputParser(pydantic_object=CourseOutline)
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a professional course editor. You will be given a course outline in JSON and an edit request. "
             "Update the outline based on the request. Do not remove unrelated sections. "
             f"{parser.get_format_instructions()}\n\n"
             "Return only clean valid JSON matching the CourseOutline schema as stated above."),
            ("human", "Original outline:\n{current_outline}\n\nEdit request:\n{edit_request}")
        ])

        chain = prompt | llm | parser
        updated_outline = chain.invoke({
            "current_outline": state["current_outline"],
            "edit_request": state["user_edit_request"]
        })

        return {
            **state,
            "course_outline": updated_outline.model_dump_json(indent=2),
            "current_content": {"outline":updated_outline.model_dump_json(indent=2)},
            "messages": list(state["messages"]) + [
                HumanMessage(content=f"{state['user_edit_request']} Current course outline is: {state['current_outline']}"),
                AIMessage(content=updated_outline.model_dump_json(indent=2))
            ],
            # "status": "feedback",  # still awaiting feedback
            "awaiting_approval": True,  # stay in approval loop until confirmed
            "step": "course_outline_generation"
        }

    # Otherwise, generate the initial course outline
    parsed_prompt: CoursePrompt = parse_user_input_for_course_outline(user_message.content)
    outline = generate_course_outline(parsed_prompt)
    outline_json = outline.model_dump_json(indent=2)

    print("\nGenerated course outline:\n", outline_json)

    return {
        **state,
        "current_content": {"outline":outline_json},
        "course_outline": outline_json,
        "messages": list(state["messages"]) + [
            HumanMessage(content=user_message.content),
            AIMessage(content=outline_json)
        ],
        "awaiting_approval": True,  # Now waiting for user input
        # "status": "feedback",       # Means: we want feedback
        # "step": "course_outline_generation"
    }


def to_edit_outline(state: AgentState)->str:
    """Determine if user wants to edit the outline or continue to the next step to generate a course."""
    print("Checking if user wants to edit outline or continue...")
    # save_recall_memory(state)
    # last_human = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    last_human = state.get("user_edit_request", None)
    if not last_human:
        return "course_generation"
    
    intent = intent_checker(last_human)
    return "edit_course_outline" if intent.strip() == "edit_outline" else "course_generation"



def course_generation_workflow_node(state: AgentState) -> AgentState:
    """
    Combined workflow for course content:
    1. If awaiting approval and user_edit_request exists → edit the current module.
    2. Else → generate the current module.
    3. If index >= len(modules) → finish course.
    """
    outline = json.loads(state["course_outline"])
    index = state.get("module_index", 0)
    modules = outline.get("modules", [])

    # --- CASE 1: All modules generated ---
    if index >= len(modules):
        print(f"Finished generating all {len(modules)} modules.")
        save_recall_memory(state)
        final_course = "\n\n".join(state.get("generated_modules", []))
        return {
            **state,
            "course": final_course,
            "messages": list(state["messages"]) + [AIMessage(content="All modules generated!")],
            "awaiting_approval": False,
            "current_content": {"outline": state["course_outline"], "course": final_course},
            # "step": "finished"
        }

    # --- CASE 2: Edit mode ---
    if state.get("awaiting_approval") and state.get("user_edit_request"):
        print("Editing current module based on user feedback...")
        current_module = modules[index]
        edit_request = state["user_edit_request"]

        edited_text = llm.invoke(
            f"Here's the original module: {json.dumps(current_module)}.\n"
            f"User requested: {edit_request}.\n"
            "Regenerate the module accordingly."
        )

        updated_modules = state.get("generated_modules", [])[:-1] + [edited_text]

        return {
            **state,
            "current_content": {"updated_module": edited_text},
            "generated_modules": updated_modules,
            "messages": list(state["messages"]) + [HumanMessage(content=state["user_edit_request"]),AIMessage(content=edited_text)],
            "awaiting_approval": True,
            "module_index": index,  # stay on this module until approved
            "user_edit_request": None
        }

    # --- CASE 3: Generation mode ---
    print(f"Generating module {index + 1}/{len(modules)}...")
    current_module = modules[index]
    module_text = generate_module_content(current_module, outline)

    updated_modules = state.get("generated_modules", []) + [module_text]

    return {
        **state,
        "current_content": {"module": module_text},
        "generated_modules": updated_modules,
        "messages": list(state["messages"]) + [AIMessage(content=module_text)],
        "awaiting_approval": True,  # wait for approval before advancing
        "module_index": index,  # stay until approved
        "user_edit_request": None,
        # "step": "course_generation"
    }

    
def check_user_feedback(state: AgentState) -> str:
    """Check user feedback on the last generated module."""
    print("Checking user feedback...")
    # save_recall_memory(state)
    if not state["awaiting_approval"]:
        return "generate_module"

    # last_msg = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    # if not last_msg:
    #     return "generate_module"
    
    last_msg = state["user_edit_request"]

    intent = check_module_feedback_intent(last_msg.content if isinstance(last_msg, HumanMessage) else last_msg)

    if intent == "approve":
        return "generate_module"
    elif intent == "edit":
        return "edit_module"
    else:
        return "generate_module"



    
def advance_module_node(state: AgentState) -> AgentState:
    """Advance to the next module or finish if all modules are done."""
    print("Advancing to next module...")
    if state["awaiting_approval"]:
        return state
    else:
        # If we are not awaiting approval, just advance
        return {
            **state,
            "module_index": state["module_index"] + 1,
            "awaiting_approval": False
        }



graph = StateGraph(state_schema=AgentState)

graph.add_node("course_outline_generation", course_outline_workflow_node)
graph.add_node("course_generation", course_generation_workflow_node)
graph.add_node("advance_module", advance_module_node)
graph.add_node("human_feedback_outline", human_feedback)
graph.add_node("human_feedback_course", human_feedback)

graph.set_entry_point("course_outline_generation")
graph.add_edge("course_outline_generation", "human_feedback_outline")
graph.add_conditional_edges(
    "human_feedback_outline",
    to_edit_outline,
    {
        "edit_course_outline": "course_outline_generation",
        "course_generation": "course_generation"
    }
)
graph.add_edge("human_feedback_outline", "course_generation")
graph.add_edge("course_generation", "human_feedback_course")
graph.add_conditional_edges(
    "human_feedback_course",
    check_user_feedback,
    {
        "generate_module": "advance_module",      # If user approves
        "edit_module": "course_generation",  # If user wants changes
        "check_user_feedback": "human_feedback_course",  # If unclear
    }
)
graph.add_conditional_edges(
    "advance_module",
    lambda state: (
        "course_generation"
        if state["module_index"] <= len(json.loads(state["course_outline"])["modules"])
        else END
    ),
    {
        "course_generation": "course_generation",
        END: END,
    }
)

memory = SupabaseCheckpointSaver(SessionLocal)
memory.setup()



agent = graph.compile(interrupt_before=["human_feedback_outline", "human_feedback_course"], checkpointer=memory)


# mermaid_code = agent.get_graph().draw_mermaid()
# Path("graph_diagram.mmd").write_text(mermaid_code)
# print("✅ Mermaid graph saved to graph_diagram.mmd")

if __name__ == "__main__":
    user_id = "user_" + str(uuid4())
    course_id = "course_" + str(uuid4())
    print(f"User ID: {user_id}, Course ID: {course_id}")

    user_message = HumanMessage(content="""
    Create a course on DSA for interviews for beginner developers.
    Target audience: Developers who want to learn Data Structures and Algorithms for interviews 
    Estimated duration: 4 weeks  
    Include code examples: Yes  
    Custom URLs: ["https://takeuforward.org/strivers-a2z-dsa-course/strivers-a2z-dsa-course-sheet-2/"]
    """)

    initial_state = {
        "user_id": user_id,
        "course_id": course_id,
        "messages": [user_message],
        "course_outline": "",
        "current_outline": None,
        "user_edit_request": None,
        "module_index": 0,
        "generated_modules": [],
        "awaiting_approval": False,
        "course": ""
    }

    config = {"configurable": {"thread_id": "1"}}

    # Start graph
    state = agent.invoke(initial_state, config)
    
    state_test = agent.get_state(config)
    pprint(state_test)

    # Approve outline
    print("Awaiting User feedback on outline")
    agent.update_state(config, {
        "user_edit_request": "Looks great! Please proceed.",
        "awaiting_approval": False
    })
    state = agent.invoke(None, config)

    # Approve each module
    while state["awaiting_approval"]:
        print("Awaiting user feedback on module")
        agent.update_state(config, {
            "user_edit_request": "Approved. Continue.",
            "awaiting_approval": False
        })
        state = agent.invoke(None, config)
    
    memory.delete_all()

    print("\n\n========== FINAL COURSE ==========\n\n")
    print(state["course"])




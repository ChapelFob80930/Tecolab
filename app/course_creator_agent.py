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
from course_outline_generation import generate_course_outline
from schemas import CourseOutline, CoursePrompt
import tiktoken
from langchain_core.runnables import RunnableConfig
import uuid
from course_outline_generation import parse_user_input_for_course_outline, generate_course_outline
from course_generation import generate_module_content
from pathlib import Path
# from vector_database import get_vector_db
from supabase import get_db
from supabase_models import AgentMemory
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import text
from typing import List
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session



load_dotenv()

embeddings = OpenAIEmbeddings()

# recall_vector_store = InMemoryVectorStore(OpenAIEmbeddings())

vector_store: Session = next(get_db())

llm = ChatOpenAI(model = "gpt-4.1-nano", temperature=0)

## HELPER FUNCTIONS

def intent_checker(message: BaseMessage):
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
    
    return intent_chain.invoke({"user_input": message.content})

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


# def get_user_id(config: RunnableConfig) -> str:
#     return config.get("configurable", {}).get("user_id", "anonymous")


## ACTUAL AGENT CODE

class AgentState(TypedDict):
    user_id: int
    course_id: str
    messages: Annotated[Sequence[BaseMessage], add_messages]
    course_outline: str
    course: str
    current_outline: Optional[str]  # for tools
    user_edit_request: Optional[str]  # for tools
    module_index: int                      # New: which module is currently being generated
    generated_modules: List[str]          # New: list of fully generated module texts
    awaiting_approval: bool               # New: whether we're waiting for user input




# @tool
# def web_scraping(content: str):
#     pass

# @tool
# def get_yt_links(content: str):
#     pass

# @tool
# def save_recall_memory(memory: AgentState, config: RunnableConfig) -> str:
def save_recall_memory(memory: AgentState) -> str:
    """Save memory(course content and course outline) to vectorstore (supabase) for later semantic retrieval whenever course content or course outline is generated or updated."""
    # agent_db = get_db()
    if not vector_store:
        raise ValueError("Database connection not established.")
    # user_id = get_user_id(config)
    # document = Document(
    #     page_content=memory, id=str(uuid.uuid4()), metadata={"user_id": user_id}
    # )
    # vector_store.add_documents([document])
    course_outline = json.dumps(memory["course_outline"]) if isinstance(memory["course_outline"], str) else memory["course_outline"]
    course_outline_embedding = embeddings.embed_query(course_outline)
    
    course_content_embedding = None
    if memory["course"]:
        course = json.dumps(memory["course"]) if isinstance(memory["course"], str) else memory["course"]
        course_content_embedding = embeddings.embed_query(course)
    
    
    
    # if "user_id" not in memory or "course_id" not in memory:
    #     raise ValueError("Missing user_id or course_id in state")

    
    new_memory = AgentMemory(
        user_id=memory["user_id"],
        course_id=memory["course_id"],
        course_outline=memory["course_outline"] if memory["course_outline"] else "",
        course_outline_embeddings=course_outline_embedding if course_outline_embedding else None,
        course_content=memory["course"] if memory["course"] else "",
        course_content_embeddings=course_content_embedding if course_content_embedding else None,
        final_course=memory["generated_modules"] if memory["generated_modules"] else "",
        final_course_outline=memory["course_outline"] if memory["course_outline"] else "",
        final_course_outline_embeddings=course_outline_embedding if course_outline_embedding else None
    )
    
    vector_store.add(new_memory)
    vector_store.commit()
    vector_store.refresh(new_memory)
    
    return memory

# @tool
# def search_recall_memories(query: str, config: RunnableConfig, user_id: int, course_id: str) -> List[str]:
def search_recall_memories(query: str, user_id: int, course_id: str) -> List[str]:
    """Search for semantically similar memory chunks when generating the course outline i.e. when the agent is initially activated."""
    # agent_db = get_db()
    query_embedding = embeddings.embed_query(query)
    if not vector_store:
        raise ValueError("Database connection not established.")
    # user_id = get_user_id(config)

    # def _filter_function(doc: Document) -> bool:
    #     return doc.metadata.get("user_id") == user_id

    # documents = vector_store.similarity_search(
    #     query, k=3, filter=_filter_function
    # )
    # return [document.page_content for document in documents]
    
    results = vector_store.execute(text("""
        SELECT course_content 
        FROM agent_memory 
        WHERE user_id = :user_id AND course_id = :course_id 
        ORDER BY course_content_embedding <-> :query_embedding 
        LIMIT 3
    """), {
        "user_id": user_id,
        "course_id": course_id,
        "query_embedding": query_embedding
    })
    
    return [row[0] for row in results]



# tools = [save_recall_memory, search_recall_memories]

# llm = ChatOpenAI(model = "gpt-4.1-nano", temperature=0).bind_tools(tools)

def course_outline_generation_node(state: AgentState)->AgentState:
    """Generate the course outline based on user input."""
    
    user_message = next((msg for msg in reversed(state["messages"]) if isinstance(msg, HumanMessage)), None)
    if not user_message:
        raise ValueError("No user message found.")

    parsed_prompt: CoursePrompt = parse_user_input_for_course_outline(user_message.content)
    outline = generate_course_outline(parsed_prompt)
    # print(type(outline))
    # print(type(outline.model_dump_json(indent=2)))
    print(outline.model_dump_json(indent=2))
    # save_recall_memory(json.dumps(outline, indent=2), config=RunnableConfig(configurable={"user_id": user_id}))
    print("\nGenerated course outline\n\n")
    
    
    
    return{
        **state,
        "current_outline": outline.model_dump_json(indent=2),
        "messages": list(state["messages"])+ [HumanMessage(content = user_message.content), AIMessage(content = outline.model_dump_json(indent=2))],
        "course_outline": outline.model_dump_json(indent=2),
        "course": state["course"]
    }
    
    
def edit_course_outline_node(current_outline: str, user_edit_request: str, state: AgentState) -> AgentState:
    """Modify the course outline JSON based on user's edit request. Takes in the original outline and user's edit request as input. Always return valid updated JSON output."""
    
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
        "current_outline": current_outline,
        "edit_request": user_edit_request
    })
    
    print(type(updated_outline))

    return {
        **state,
        "course_outline": updated_outline.model_dump_json(indent=2),
        "current_outline": updated_outline.model_dump_json(indent=2),
        "user_edit_request": user_edit_request,
        "messages": list(state["messages"]) + [HumanMessage(content = user_edit_request + "Current course outline is: " + current_outline), AIMessage(content = updated_outline.model_dump_json(indent=2))]
        }

def to_edit_outline_node(state: AgentState)->str:
    """Determine if user wants to edit the outline or continue to the next step to generate a course."""
    save_recall_memory(state)
    last_human = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    if not last_human:
        return "course_generation"
    
    intent = intent_checker(last_human)
    return "edit_course_outline" if intent.strip() == "edit_outline" else "course_generation"

def to_generate_course_node(state: AgentState) -> AgentState:
    outline = json.loads(state["course_outline"])
    index = state.get("module_index", 0)
    modules = outline.get("modules", [])

    if index >= len(modules):
        print(f"finished generating module content for module {index} of {len(modules)}\n\n")
        final_course = "\n\n".join(state.get("generated_modules", []))
        # print(final_course)
        return {
            **state,
            "course": final_course,
            "messages": list(state["messages"]) + [AIMessage(content="🎉 All modules generated!")],
            "awaiting_approval": False
        }

    
    current_module = modules[index]
    module_text = generate_module_content(current_module, outline)
    
    print(module_text +"\n\n")
    
    print(f"finished generating module content for module {index} of {len(modules)}")
    
    
    # print(state["generated_modules"])
    
    print("\n\n")

    return {
        **state,
        "generated_modules": state.get("generated_modules", []) + [module_text],
        "messages": list(state["messages"]) + [AIMessage(content=module_text)],
        "awaiting_approval": True,
        "module_index": index  # stay on this module until approved
    }

    
def check_user_feedback_node(state: AgentState) -> str:
    """Check user feedback on the last generated module."""
    save_recall_memory(state)
    if not state["awaiting_approval"]:
        return "generate_module"

    last_msg = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    if not last_msg:
        return "generate_module"

    intent = check_module_feedback_intent(last_msg.content)

    if intent == "approve":
        return "generate_module"
    elif intent == "edit":
        return "edit_module"
    else:
        return "check_user_feedback"


def edit_current_module_node(state: AgentState) -> AgentState:
    """Edit the last generated module based on user feedback."""
    outline = json.loads(state["course_outline"])
    index = state["module_index"]
    modules = outline.get("modules", [])

    current_module = modules[index]
    edit_request = state["user_edit_request"] or "Apply the user's suggestion."

    # You can add a custom prompt here too
    edited_text = llm.invoke(f"Here's the original module: {json.dumps(current_module)}.\nUser requested: {edit_request}.\nRegenerate the module accordingly.")

    # Replace last generated module with new one
    updated_modules = state["generated_modules"][:-1] + [edited_text]

    return {
        **state,
        "generated_modules": updated_modules,
        "messages": list(state["messages"]) + [AIMessage(content=edited_text)],
        "awaiting_approval": True
    }
    
def advance_module_node(state: AgentState) -> AgentState:
    return {
        **state,
        "module_index": state["module_index"] + 1,
        "awaiting_approval": False
    }



graph = StateGraph(AgentState)

# --- Step 1: Add Nodes ---
graph.add_node("course_outline_generation", course_outline_generation_node)
graph.add_node("edit_course_outline", edit_course_outline_node)
# graph.add_node("to_edit_outline", to_edit_outline_node)
# graph.add_node("tools", ToolNode(tools))

graph.add_node("course_generation", to_generate_course_node)
# graph.add_node("check_user_feedback", check_user_feedback_node)
graph.add_node("edit_module", edit_current_module_node)
graph.add_node("advance_module", advance_module_node)

# Set Entry Point ---
graph.set_entry_point("course_outline_generation")

# graph.add_edge("tools", "course_outline_generation")

# graph.add_edge("course_outline_generation", "tools")

# After outline generation, check user intent ---
graph.add_conditional_edges(
    "course_outline_generation",
    to_edit_outline_node,
    {
        "edit_course_outline": "edit_course_outline",
        "course_generation": "course_generation"
    }
)

# graph.add_edge("course_outline_generation", "to_edit_outline")
# graph.add_edge("edit_course_outline", "to_edit_outline")

graph.add_conditional_edges(
    "edit_course_outline",
    to_edit_outline_node,
    {
        "edit_course_outline": "edit_course_outline",
        "course_generation": "course_generation"
    }
)
    


# After editing outline, regenerate course ---
graph.add_edge("edit_course_outline", "course_generation")

# After generating a module, check user feedback ---
# graph.add_edge("course_generation", "check_user_feedback")

graph.add_conditional_edges(
    "course_generation",
    check_user_feedback_node,
    {
        "generate_module": "advance_module",      # If user approves
        "edit_module": "edit_module",             # If user wants changes
        # "check_user_feedback": "check_user_feedback",  # If unclear
    }
)

#  After editing a module, re-check user feedback ---
# graph.add_edge("edit_module", "check_user_feedback")
graph.add_conditional_edges(
    "edit_module",
    check_user_feedback_node,
    {
        "generate_module": "advance_module",      # If user approves
        "edit_module": "edit_module",             # If user wants changes
        # "check_user_feedback": "check_user_feedback",  # If unclear
    }
)

#  If unclear feedback, ask again (loop) ---
# graph.add_edge("check_user_feedback", "course_generation")

#  After user approves a module, move to next or finish ---
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



agent = graph.compile()

# mermaid_code = agent.get_graph().draw_mermaid()
# Path("graph_diagram.mmd").write_text(mermaid_code)
# print("✅ Mermaid graph saved to graph_diagram.mmd")


# Temporary fix to run the agent with a dummy input until the actual API is set up
# if __name__ == "__main__":
#     user_message = HumanMessage(content="""
#     Create a course on LangChain Agents for intermediate developers.

#     Target audience: Developers who are familiar with Python and want to learn AI agents  
#     Estimated duration: 4 weeks  
#     Include code examples: Yes  
#     Custom URLs: ["https://python.langchain.com", "https://docs.smith.langchain.com"]
#     """)

#     initial_state = {
#         "messages": [user_message],
#         "course_outline": "",
#         "course": "",
#         "current_outline": None,
#         "user_edit_request": None,
#         "module_index": 0,
#         "generated_modules": [],
#         "awaiting_approval": False
#     }

#     state = agent.invoke(initial_state)

#     print("\n\n========== GENERATED COURSE ==========\n\n")
#     print(state["course"])

if __name__ == "__main__":
    user_id = uuid4()
    course_id = str(uuid4())
    print(f"User ID: {user_id}, Course ID: {course_id}")

    # Human message prompting course generation
    user_message = HumanMessage(content=f"""
    Create a course on LangChain Agents for intermediate developers.

    Target audience: Developers who are familiar with Python and want to learn AI agents  
    Estimated duration: 4 weeks  
    Include code examples: Yes  
    Custom URLs: ["https://python.langchain.com", "https://docs.smith.langchain.com"]
    """)

    # Initial state passed into the agent
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
        "course": ""  # New: to store the final course content
    }

    # Invoke the agent with the state
    state = agent.invoke(initial_state)

    # Output the final course
    print("\n\n========== GENERATED COURSE ==========\n\n")
    print(state["course"])

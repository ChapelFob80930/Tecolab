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

load_dotenv()

recall_vector_store = InMemoryVectorStore(OpenAIEmbeddings())

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


def generate_course_outline(prompt: CoursePrompt):
    """Generates a course outline as per the users specifications"""
    
    print("Generating course outline\n\n")
    
    parser = PydanticOutputParser(pydantic_object=CourseOutline)


    prompt_template = ChatPromptTemplate.from_messages([
        ("system", 
        "You are an expert technical course designer. Generate high-quality, structured, and project-based tech course outlines. "
        "Ensure the content is modular, developer-friendly, and production-ready."),
        
        ("user", 
        """Create a course on **"{topic}"** for a **{level}** learner.

    Target audience: {audience}  
    Estimated duration: {duration}  
    Include code examples: {include_code}  
    Custom URLs provided: {custom_urls}  

    ➡️ If `include_code` is true:
    - Add a `code_examples` field to each module.
    - Instead of just "Yes", describe what kind of code examples should be included 
        (e.g., "LangChain chains", "Retrieval QA pipeline", "Tool agent example").
    - If no code is needed, set it as "No".

    ➡️ If `custom_urls` are provided:
    - Add a `scraping_resources` field to each module.
    - It should be a dictionary mapping resource types (like "docs", "blog", "video") to the most relevant URLs **per module**.
    - You may include:
        - URLs from `custom_urls` if they apply to that module
        - Any other public, legally scrapeable resources GPT is aware of (e.g., official docs, blogs, public GitHub files, videos)
    - Prioritize relevance and usefulness for that module.

    ➡️ For the `resources` field:
    - Set it as a dictionary like: {{"docs": "...", "blog": "...", "toolkit": "..."}}
    - Do not return a list.
    - If no resources are found, return an empty dictionary (`{{}}`).

    ➡️ For video links:
    - Only include **real, publicly available video links** (YouTube, Vimeo, etc).
    - ❌ Never include placeholders or obviously fake video URLs like:
        - "https://www.youtube.com/watch?v=example"
        - "https://www.youtube.com/watch?v=V7V7V7V7V7V"
        - "https://youtube.com/watch?v=ZZZZZZZZZZZ"
        - Or anything that looks auto-generated or doesn’t lead to a real video.
    - ✅ If no real videos are found, set `video_links` as an empty list (`[]`).

    🛑 Do NOT include inline comments in JSON like `// placeholder` — return clean, valid JSON only.

    ---

    Return ONLY a structured JSON output with the following fields:

    1. `title` — a compelling title for the course  
    2. `description` — what the course offers  
    3. `modules` — a list of modules. Each module must include:
    - `title`  
    - `summary`  
    - `code_examples` (short descriptive string)  
    - `resources` (dictionary of helpful links like: {{"docs": "...", "blog": "..."}})  
    - `video_links` (list of real YouTube/Vimeo video URLs, or empty list)  
    - `scraping_resources` (dictionary of scrapeable URLs by type: {{"docs": "...", "video": "...", "blog": "..."}})

    4. `prerequisites` — list of concepts the learner should already know  
    5. `will_learn` — list of outcomes or skills gained  
    6. `estimated_time` — how long this course will take  
    7. `module_difficulty` — dictionary where each key is a module title and the value is its difficulty level (`"Easy"`, `"Medium"`, or `"Hard"`)

    Example:
    ```json
    {{
    "module_difficulty": {{
        "Introduction to LangChain": "Easy",
        "Prompt Engineering in LangChain": "Medium",
        "Building Agents with Tools": "Hard"
    }}
    }}
    """)
    ])

    input_values = {
            "topic": prompt.topic,
            "level": prompt.level,
            "use_scraping": prompt.use_scraping, # scraping is disabled for now
            "include_code": prompt.include_code,
            "audience": prompt.audience or "general learners",
            "duration": prompt.duration or "auto",
            "include_code": "yes" if prompt.include_code else "no",
            "custom_urls": prompt.custom_urls
    }
    
    chain = prompt_template|llm|parser
    
    
    return chain.invoke(input_values)

def generate_module_content(module: dict, full_outline: dict) -> str:
    """
    Expand a single module into a fully detailed lesson using full outline context.
    """

    print("Generating module content")

    prompt = ChatPromptTemplate.from_messages([
        ("system", 
         "You are a professional technical course creator. Your job is to expand individual modules "
         "from a course outline into rich, structured educational content. You're allowed to creatively "
         "add relevant subtopics and tasks if they benefit the learner."),
        ("user", 
         "Here is the full course outline for context:\n\n{outline}\n\n"
         "Now generate the full lesson content for the following module:\n\n{module}\n\n"
         "Please include:\n"
         "- Detailed explanation of each subtopic\n"
         "- Code examples (from outline or inferred)\n"
         "- Real-world applications\n"
         "- Links to resources\n"
         "- Hands-on exercises or practice tasks\n")
    ])
    
    # print(type(full_outline))
    # print(type(module))

    chain = prompt | llm | StrOutputParser()
    return chain.invoke({
        "outline": full_outline,
        "module": module
    })


def parse_user_input_for_course_outline(user_input: str)->CoursePrompt: #named this way as might have to make another to parse input for course generation if we make specified schema for that
    """parse the user input into the desired format to generate course outline"""
    llm_structured_output = llm.with_structured_output(CoursePrompt)
    return llm_structured_output.invoke(user_input)

def get_user_id(config: RunnableConfig) -> str:
    return config.get("configurable", {}).get("user_id", "anonymous")


## ACTUAL AGENT CODE

class AgentState(TypedDict):
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

def save_recall_memory(memory: str, config: RunnableConfig) -> str:
    """Save memory to vectorstore for later semantic retrieval."""
    user_id = get_user_id(config)
    document = Document(
        page_content=memory, id=str(uuid.uuid4()), metadata={"user_id": user_id}
    )
    recall_vector_store.add_documents([document])
    return memory



def search_recall_memories(query: str, config: RunnableConfig) -> List[str]:
    """Search for relevant memories."""
    user_id = get_user_id(config)

    def _filter_function(doc: Document) -> bool:
        return doc.metadata.get("user_id") == user_id

    documents = recall_vector_store.similarity_search(
        query, k=3, filter=_filter_function
    )
    return [document.page_content for document in documents]


# tools = [edit_course_outline, save_recall_memory, search_recall_memories]

# llm_with_tools = ChatOpenAI(model = "gpt-4.1-nano", temperature=0).bind_tools(tools)

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
        "messages": list(state["messages"]) + [HumanMessage(content = user_edit_request + "Current course outline is: " + current_outline), AIMessage(content = updated_outline.model_dump_json(indent=2))]
        }

def to_edit_outline_node(state: AgentState)->str:
    """Determine if user wants to edit the outline or continue to the next step to generate a course."""
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
graph.add_node("to_edit_outline", to_edit_outline_node)

graph.add_node("course_generation", to_generate_course_node)
graph.add_node("check_user_feedback", check_user_feedback_node)
graph.add_node("edit_module", edit_current_module_node)
graph.add_node("advance_module", advance_module_node)

# Set Entry Point ---
graph.set_entry_point("course_outline_generation")

# After outline generation, check user intent ---
graph.add_conditional_edges(
    "course_outline_generation",
    to_edit_outline_node,
    {
        "edit_course_outline": "edit_course_outline",
        "course_generation": "course_generation"
    }
)

# After editing outline, regenerate course ---
graph.add_edge("edit_course_outline", "course_generation")

# After generating a module, check user feedback ---
graph.add_conditional_edges(
    "course_generation",
    check_user_feedback_node,
    {
        "generate_module": "advance_module",      # If user approves
        "edit_module": "edit_module",             # If user wants changes
        "check_user_feedback": "check_user_feedback",  # If unclear
    }
)

#  After editing a module, re-check user feedback ---
graph.add_edge("edit_module", "check_user_feedback")

#  If unclear feedback, ask again (loop) ---
graph.add_edge("check_user_feedback", "course_generation")

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


## Temporary fix to run the agent with a dummy input until the actual API is set up
if __name__ == "__main__":
    user_message = HumanMessage(content="""
    Create a course on LangChain Agents for intermediate developers.

    Target audience: Developers who are familiar with Python and want to learn AI agents  
    Estimated duration: 4 weeks  
    Include code examples: Yes  
    Custom URLs: ["https://python.langchain.com", "https://docs.smith.langchain.com"]
    """)

    initial_state = {
        "messages": [user_message],
        "course_outline": "",
        "course": "",
        "current_outline": None,
        "user_edit_request": None,
        "module_index": 0,
        "generated_modules": [],
        "awaiting_approval": False
    }

    state = agent.invoke(initial_state)

    print("\n\n========== GENERATED COURSE ==========\n\n")
    print(state["course"])
from typing import Annotated, Sequence, List, Literal, Optional
from typing_extensions import TypedDict
from dotenv import load_dotenv
import os
import json
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from . import database, schemas, models, utils, oauth2
from .config import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    BaseMessage,
    ToolMessage,
    SystemMessage,
    HumanMessage,
    get_buffer_string
)
from langchain_core.tools import tool
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_tavily import TavilySearch
from .course_outline_generation import generate_course_outline
from schemas import CourseOutline, CoursePrompt
import tiktoken
from langchain_core.runnables import RunnableConfig
import uuid

load_dotenv()

recall_vector_store = InMemoryVectorStore(OpenAIEmbeddings())


def get_user_id(config: RunnableConfig) -> str:
    return config.get("configurable", {}).get("user_id", "anonymous")

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    course_outline: str
    course: str

@tool
def generate_course_outline(prompt: CoursePrompt):
    """Generates a course outline as per the users specifications"""
    
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

@tool
def web_scraping(content: str):
    pass

@tool
def get_yt_links(content: str):
    pass

@tool
def save_recall_memory(memory: str, config: RunnableConfig) -> str:
    """Save memory to vectorstore for later semantic retrieval."""
    user_id = get_user_id(config)
    document = Document(
        page_content=memory, id=str(uuid.uuid4()), metadata={"user_id": user_id}
    )
    recall_vector_store.add_documents([document])
    return memory


@tool
def search_recall_memories(query: str, config: RunnableConfig) -> List[str]:
    """Search for relevant memories."""
    user_id = get_user_id(config)

    def _filter_function(doc: Document) -> bool:
        return doc.metadata.get("user_id") == user_id

    documents = recall_vector_store.similarity_search(
        query, k=3, filter=_filter_function
    )
    return [document.page_content for document in documents]

@tool
def parse_user_input_for_course_outline(user_input: str)->CoursePrompt: #named this way as might have to make another to parse input for course generation if we make specified schema for that
    """parse the user input into the desired format to generate course outline"""
    llm_structured_output = llm.with_structured_output(CoursePrompt)
    return llm_structured_output.invoke(user_input)

tools = [generate_course_outline, save_recall_memory, search_recall_memories, parse_user_input_for_course_outline]

llm = ChatOpenAI(model = "gpt-4.1-nano", temperature=0)

llm_with_tools = ChatOpenAI(model = "gpt-4.1-nano", temperature=0).bind_tools(tools)

def course_outline_generation_node(state: AgentState)->AgentState:
    if not state['messages']:
        user_input = "I'm ready to help you create your own courses. What would you like to create?"
        user_message = HumanMessage(content=user_input)
    
    
    pass

def to_edit_outline_node(state: AgentState)->AgentState:
    pass

def to_generate_course_node(state: AgentState)->AgentState:
    pass

def to_edit_course_node(state: AgentState)->AgentState:
    pass

graph = StateGraph(AgentState)
graph.add_node("course_outline_generation", course_outline_generation_node)
graph.add_node("course_generation", to_generate_course_node)
graph.add_node("tools", ToolNode(tools))
# graph.add_node("course_generation", generate_course_outline)
# graph.add_node("course_generation", generate_course_outline)
graph.add_conditional_edges(
    "course_outline_generation",
    to_edit_outline_node,
    {
        
    }
)
graph.add_conditional_edges(
    "course_generation",
    to_edit_course_node,
    {
        
    }
)
agent = graph.compile()
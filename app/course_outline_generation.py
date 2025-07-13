from schemas import CourseOutline, CoursePrompt
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage 
import os
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

llm = ChatOpenAI(model = "gpt-4.1-nano", temperature=0)

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

def generate_course_outline(prompt: CoursePrompt) -> CourseOutline:
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

    chain = prompt_template | llm | parser
    return chain.invoke(input_values)

if __name__ == "__main__":
    test_prompt = CoursePrompt(
    topic="LangChain",
    level="intermediate",
    audience="AI engineers",
    duration="3 weeks",
    include_code=True,
    custom_urls=["https://docs.langchain.com/docs/", "https://python.langchain.com/docs/modules/agents/"]
)

    outline = generate_course_outline(test_prompt)
    print(outline.model_dump_json(indent=2))

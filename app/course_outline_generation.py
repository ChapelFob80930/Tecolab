from schemas import CourseOutline, CoursePrompt
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage 
import os
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

llm = ChatOpenAI(model = "gpt-4.1-nano")

parser = PydanticOutputParser(pydantic_object=CourseOutline)

# Prompt template
prompt_template = ChatPromptTemplate.from_messages([
    ("system", "You are an expert course designer. Generate high-quality, project-based course outlines."),
    ("user", """
Create a course on "{topic}" for a {level} learner.
Audience: {audience}
Duration: {duration}
Include code examples: {include_code}

Return structured output with:
- title
- description
- modules (title + summary)
- prerequisites
- will_learn
""")
])

def generate_course_outline(prompt: CoursePrompt) -> CourseOutline:
    input_values = {
        "topic": prompt.topic,
        "level": prompt.level,
        # "use_scraping": prompt.use_scraping,
        "audience": prompt.audience or "general learners",
        "duration": prompt.duration or "auto",
        "include_code": "yes" if prompt.include_code else "no"
    }

    chain = prompt_template | llm | parser
    return chain.invoke(input_values)

if __name__ == "__main__":
    test_prompt = CoursePrompt(
        topic="LangChain",
        level="intermediate",
        # use_scraping=True,
        audience="early-stage AI startup founders",
        duration="2 weeks",
        include_code=True
    )

    outline = generate_course_outline(test_prompt)
    print(outline.model_dump_json(indent=2))

##NOTE: This code is part of a larger application and is designed to generate detailed educational content for a course module based on a provided outline. It uses the LangChain library to interact with an LLM (Language Model) and generate structured content. And it is just for testing purposes. Might use as a separate module in the future.

from schemas import CourseOutline, CoursePrompt
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage 
import os
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from course_outline_generation import generate_course_outline, parse_user_input_for_course_outline

load_dotenv()



llm = ChatOpenAI(model = "gpt-4.1-nano", temperature=0)
# def generate_module_content(module: dict, full_outline: dict) -> str:
#     """
#     Expand a single module into a fully detailed lesson using full outline context.
#     """

#     prompt = ChatPromptTemplate.from_messages([
#         ("system", 
#          "You are a professional technical course creator. Your job is to expand individual modules "
#          "from a course outline into rich, structured educational content. You're allowed to creatively "
#          "add relevant subtopics and tasks if they benefit the learner."),
#         ("user", 
#          "Here is the full course outline for context:\n\n{outline}\n\n"
#          "Now generate the full lesson content for the following module:\n\n{module}\n\n"
#          "Please include:\n"
#          "- Detailed explanation of each subtopic\n"
#          "- Code examples (from outline or inferred)\n"
#          "- Real-world applications\n"
#          "- Links to resources\n"
#          "- Hands-on exercises or practice tasks\n")
#     ])

#     chain = prompt | llm | StrOutputParser()
#     return chain.invoke({
#         "outline": full_outline.model_dump_json(indent=2),
#         "module": module.model_dump_json(indent=2)
#     })

# if __name__ == "__main__":
#     # Use the same input to keep context consistent
#     user_input = (
#         "I want a course on LangChain for intermediate-level AI engineers. "
#         "It should last 3 weeks and include code examples. Use these URLs: "
#         "https://docs.langchain.com/docs/, https://python.langchain.com/docs/modules/agents/"
#     )

#     # Generate the full outline
#     prompt = parse_user_input_for_course_outline(user_input)
#     outline = generate_course_outline(prompt)

#     # Select a module to expand
#     if outline.modules:
#         first_module = outline.modules[0]
#         print(f"\n📘 Expanding Module: {first_module.title}")

#         full_content = generate_module_content(first_module, outline)
#         print("\n🎓 Generated Module Content:\n")
#         print(full_content)
#     else:
#         print("❌ No modules found to expand.")

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

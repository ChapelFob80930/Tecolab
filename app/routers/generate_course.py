# from typing import List
# from fastapi import APIRouter, Depends, HTTPException, Request, status
# from sqlalchemy.orm import Session
# from .. import database, schemas, models, utils, oauth2
# from ..course_creator_agent import agent
# from uuid import uuid4
# import json
# from ..config import settings

# router = APIRouter(prefix = "/generate", tags = ['generate_course'])

# @router.post("/")
# async def generate_course_route(
#     request: Request,
#     db: Session = Depends(database.get_db),
#     current_admin: schemas.Admin = Depends(oauth2.get_current_admin) ##NOTE: nothing in this line is defined when you come back define everything in this line
# ):
    
#     ##NOTE: everything below is a placeholder so i have a basic idea of what to do, you need to implement the actual logic for generating a course using the agent
#     try:
#         user_id = str(current_admin.id)  # ✅ Admin from JWT
        
#         # 🔹 Step 1: Get prompt content from request body
#         body = await request.json()
#         user_prompt = body.get("prompt")
#         if not user_prompt:
#             raise HTTPException(status_code=400, detail="Missing 'prompt' in request body")

#         # 🔹 Step 2: Run the LangGraph agent
#         response = agent.invoke(
#             input={
#                 "messages": [{"type": "human", "content": user_prompt}],
#                 "course_outline": "",
#                 "course": ""
#             },
#             config={
#                 "configurable": {
#                     "user_id": user_id  # Injected into tools for vector memory
#                 }
#             }
#         )

#         # 🔹 Step 3: Return the output
#         return {
#             "success": True,
#             "course_outline": json.loads(response["course_outline"]),
#             "raw_output": response
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
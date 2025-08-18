from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from .. import supabase, schemas, supabase_models, utils, oauth2
from uuid import uuid4
import json
from ..config import settings
from ..agent2 import agent
from ..schemas import StartRequest, GraphResponse, ResumeRequest
import logging

logger = logging.getLogger("tecolab_app")

router = APIRouter(prefix = "/course_agent", tags = ['Course Agent'])

def run_graph_and_response(input_state, config):
    try:
        logger.debug(f"Invoking agent with input_state={input_state}, config={config}")
        result = agent.invoke(input_state, config)
        state = agent.get_state(config)
    
    except Exception as e:    
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph execution failed: {str(e)}"
        )
        
    next_nodes = state.next
    thread_id = config["configurable"]["thread_id"]
    if next_nodes and "human_feedback" in next_nodes:
        run_status = "user_feedback"
    else:
        run_status = "finished"
        
    logger.info(f"[GRAPH] run completed | thread_id={thread_id}, run_status={run_status}")
    
    return GraphResponse(
        thread_id=thread_id,
        run_status=run_status,
        assistant_response=result.get("assistant_response", ""),
    )

@router.post("/start", response_model=GraphResponse)
def start_graph(request: StartRequest, current_user = Depends(oauth2.admin_only)):
    thread_id = "thread_"+str(uuid4())
    course_id = "course_"+str(uuid4())
    if not request.human_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Human request is required to start the graph."
        )
    logger.info(f"[START] user_id={current_user.id}, thread_id={thread_id}, course_id={course_id}")
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "user_id": current_user.id,
        "course_id": course_id,
        "messages": request.human_request,
        "course_outline": "",
        "current_outline": None,
        "user_edit_request": None,
        "module_index": 0,
        "generated_modules": [],
        "awaiting_approval": False,
        "course": ""
    }
    logger.debug(f"Initial state: user_id={current_user.id}, course_id={course_id}, messages_preview={request.human_request[:100]}")
    return run_graph_and_response(initial_state, config)

@router.post("/resume", response_model=GraphResponse)
def resume_graph(request: ResumeRequest, current_user = Depends(oauth2.admin_only)):
    if not request.thread_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread ID is required to resume the graph, Thread ID not found."
        )
    config = {"configurable": {"thread_id": request.thread_id}}
    state = {"status": request.review_action}
    
    if request.user_edit_request is None:
        logger.warning(f"Invalid resume request: {request}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request. Use 'accept' to approve or 'reject' with comments to request changes."
        )
    else:
        state["user_edit_request"] = request.user_edit_request
    
    logger.info(f"[RESUME] Request to resume graph for thread_id={request.thread_id} by user_id={current_user.id}")
    
    logger.debug(f"Updating state: {state}")
    agent.update_state(config, state)

    
    return run_graph_and_response(None, config)

@router.get("/status/{thread_id}", response_model=GraphResponse)
def get_graph_status(thread_id: str, current_user=Depends(oauth2.admin_only)):
    logger.info(f"[STATUS] Checking status for thread_id={thread_id} by user_id={current_user.id}")
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = agent.get_state(config)
    except Exception as e:
        logger.error(f"Thread not found: {thread_id}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread not found: {str(e)}"
        )

    next_nodes = state.next
    run_status = "user_feedback" if next_nodes and "human_feedback" in next_nodes else "finished"
    
    logger.info(f"[STATUS] thread_id={thread_id}, run_status={run_status}")
    return GraphResponse(thread_id=thread_id, run_status=run_status)


from langgraph.graph import StateGraph, END
from graph_agentic.state import VideoState
from graph_agentic.nodes import director, plan_critic, generator, video_critic

def route_after_generator(state: VideoState):
    """
    Decides the next step after the Generator finishes.
    Iteration 1: Go to Video Critic for analysis.
    Iteration 2+: The 'readjustment' is done, go to END.
    """
    if state["iterations"] == 1:
        print("🔍 [Graph] First draft complete. Sending to Video Critic...")
        return "video_critic"

    print("✅ [Graph] Final readjustment complete. Pipeline ending.")
    return END


def route_after_video_critic(state: VideoState):
    """
    Decides the next step after Video Critic finishes.
    If PASS: End the pipeline early.
    Otherwise: Go back to generator for readjustment.
    """
    feedback = state.get("visual_feedback", "")
    if "PASS" in feedback.upper():
        print("✅ [Graph] Video passed! No readjustment needed.")
        return END
    print("🔄 [Graph] Video needs readjustment. Going back to generator...")
    return "generator"

def build_graph():
    # Initialize the graph with our state schema
    workflow = StateGraph(VideoState)

    # Add the defined nodes
    workflow.add_node("director", director)
    workflow.add_node("plan_critic", plan_critic)
    workflow.add_node("generator", generator)
    workflow.add_node("video_critic", video_critic)

    # 1. Entry point
    workflow.set_entry_point("director")

    # 2. Planning phase
    workflow.add_edge("director", "plan_critic")
    workflow.add_edge("plan_critic", "generator")
    
    # 3. Decision point after Generation
    workflow.add_conditional_edges(
        "generator",
        route_after_generator,
        {
            "video_critic": "video_critic",
            END: END
        }
    )
    
    # 4. Decision point after Video Critic
    # If PASS: End early. Otherwise: Go back to generator for readjustment.
    workflow.add_conditional_edges(
        "video_critic",
        route_after_video_critic,
        {
            "generator": "generator",
            END: END
        }
    )

    return workflow.compile()